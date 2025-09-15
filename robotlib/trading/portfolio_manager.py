"""
Модуль для управления портфелем и позициями
"""
import asyncio

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from robotlib.trading.tinkoff_api_client import TinkoffAPIClient, OrderResult
from robotlib.trading.events import EventType, TradingEvent
from robotlib.utils.money import Money
from robotlib.utils.logger import get_logger
from config_data.config import load_config
from tinkoff.invest.schemas import Operation
from tinkoff.invest import OperationsRequest


@dataclass
class Position:
    """Информация о позиции по фьючерсу (в рублях)"""
    figi: str
    quantity: int
    average_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float


@dataclass
class Portfolio:
    """Информация о портфеле (фьючерсы в рублях)"""
    total_amount: float
    blocked_amount: float
    available_amount: float
    positions: List[Position]
    variation_margin: float = 0.0  # Вариационная маржа (прибыль/убыток от позиций)
    guarantee_deposit: float = 0.0  # Гарантийное обеспечение (ГО)
    pnl: float = 0.0  # Общая прибыль/убыток (P&L)


class PortfolioManager:
    """Класс для управления портфелем и позициями"""
    
    def __init__(self, api_client: TinkoffAPIClient, event_bus: Optional[object] = None):
        """
        Инициализация менеджера портфеля
        
        Args:
            api_client: API клиент для работы с Tinkoff
            event_bus: Шина событий для публикации событий (только для визуализации)
        """
        self._api_client = api_client
        self._event_bus = None
        self.logger = get_logger(__name__)
        
        # Кэш позиций
        self._positions_cache: Dict[str, Position] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = 30  # Время жизни кэша в секундах
    
    async def get_portfolio(self, force_refresh: bool = False) -> Portfolio:
        """
        Получает информацию о портфеле (фьючерсы)
        
        Args:
            force_refresh: Принудительно обновить кэш
            
        Returns:
            Portfolio с информацией о портфеле (только фьючерсы)
        """
        try:
            # Проверяем кэш
            if not force_refresh and self._is_cache_valid():
                return self._build_portfolio_from_cache()
            
            # Получаем портфель через API клиент
            response = await self._api_client.get_portfolio()
            if not response:
                return Portfolio(
                    total_amount=0.0,
                    blocked_amount=0.0,
                    available_amount=0.0,
                    positions=[]
                )
            
            # Обрабатываем позиции
            positions = []
            
            # Получаем общую сумму портфеля
            total_amount = Money(response.total_amount_portfolio).to_float()
            
            # Для заблокированной суммы используем разность между общей и доступной
            # Пока что устанавливаем в 0, так как нет прямого поля
            blocked_amount = 0.0
            
            # Обрабатываем позиции (ищем фьючерсы)
            for position_data in response.positions:
                # Проверяем, что это фьючерс
                if hasattr(position_data, 'instrument_type') and position_data.instrument_type == 'futures':
                    position = await self._process_position_data(position_data)
                    if position:
                        positions.append(position)
                        self._positions_cache[position.figi] = position
            
            # Обновляем кэш
            self._cache_timestamp = datetime.now()
            
            # Доступная сумма = общая сумма - заблокированная
            available_amount = total_amount - blocked_amount
            
            # Рассчитываем вариационную маржу, ГО и P&L
            variation_margin = 0.0
            guarantee_deposit_total = 0.0
            total_pnl = 0.0
            
            for position in positions:
                # Получаем гарантийное обеспечение для каждой позиции
                guarantee_deposit = await self.get_guarantee_deposit(position.figi)
                # ГО = количество позиций * гарантийное обеспечение
                position_go = abs(position.quantity) * guarantee_deposit
                guarantee_deposit_total += position_go
                
                # Вариационная маржа = нереализованная прибыль/убыток
                variation_margin += position.unrealized_pnl
                
                # P&L = общая прибыль/убыток (реализованная + нереализованная)
                total_pnl += position.realized_pnl + position.unrealized_pnl
            
            portfolio = Portfolio(
                total_amount=total_amount,
                blocked_amount=blocked_amount,
                available_amount=available_amount,
                positions=positions,
                variation_margin=variation_margin,
                guarantee_deposit=guarantee_deposit_total,
                pnl=total_pnl
            )
            
            self.logger.info(
                f"Портфель обновлен: {total_amount:.2f} руб, "
                f"доступно: {portfolio.available_amount:.2f} руб, "
                f"позиций: {len(positions)}"
            )
            
            # EventBus удален: обновление портфеля не транслируется через шину
            
            return portfolio
            
        except Exception as e:
            self.logger.error(f"Ошибка получения портфеля: {e}")
            return Portfolio(
                total_amount=0.0,
                blocked_amount=0.0,
                available_amount=0.0,
                positions=[],
                variation_margin=0.0,
                guarantee_deposit=0.0,
                pnl=0.0
            )
    
    async def get_position(self, figi: str) -> Optional[Position]:
        """
        Получает информацию о конкретной позиции по фьючерсу
        
        Args:
            figi: FIGI фьючерса (например, "FUTIMOEXF000")
            
        Returns:
            Position или None если позиция не найдена
        """
        portfolio = await self.get_portfolio()
        
        for position in portfolio.positions:
            if position.figi == figi:
                return position
        
        return None
    
    async def get_available_quantity(self, figi: str) -> int:
        """
        Получает доступное количество фьючерсов для торговли
        
        Args:
            figi: FIGI фьючерса (например, "FUTIMOEXF000")
            
        Returns:
            Доступное количество лотов фьючерсов
        """
        position = await self.get_position(figi)
        
        if position is None:
            return 0
        
        return abs(position.quantity)
    
    async def can_buy(self, figi: str, quantity: int, price: float) -> bool:
        """
        Проверяет, можно ли купить указанное количество фьючерсов
        
        Args:
            figi: FIGI фьючерса (например, "FUTIMOEXF000")
            quantity: Количество лотов фьючерсов
            price: Цена за лот
            
        Returns:
            True если покупка возможна, False иначе
        """
        portfolio = await self.get_portfolio()
        
        # Проверяем доступные средства
        required_amount = quantity * price
        if required_amount > portfolio.available_amount:
            self.logger.debug(
                f"Недостаточно средств для покупки: "
                f"требуется {required_amount:.2f}, доступно {portfolio.available_amount:.2f}"
            )
            return False
        
        return True
    
    async def can_sell(self, figi: str, quantity: int) -> bool:
        """
        Проверяет, можно ли продать указанное количество фьючерсов
        
        Args:
            figi: FIGI фьючерса (например, "FUTIMOEXF000")
            quantity: Количество лотов фьючерсов
            
        Returns:
            True если продажа возможна, False иначе
        """
        position = await self.get_position(figi)
        
        if position is None:
            self.logger.warning(f"Позиция по {figi} не найдена")
            return False
        
        if abs(position.quantity) < quantity:
            self.logger.warning(
                f"Недостаточно лотов для продажи: "
                f"требуется {quantity}, доступно {abs(position.quantity)}"
            )
            return False
        
        return True
    
    async def close_position(self, figi: str) -> OrderResult:
        """
        Закрывает позицию по фьючерсу
        
        Args:
            figi: FIGI фьючерса (например, "FUTIMOEXF000")
            
        Returns:
            OrderResult с результатом выполнения
        """
        position = await self.get_position(figi)
        
        if position is None:
            return OrderResult(
                success=False,
                error_message=f"Позиция по {figi} не найдена"
            )
        
        if position.quantity == 0:
            return OrderResult(
                success=True,
                error_message="Позиция уже закрыта"
            )
        
        quantity = abs(position.quantity)
        
        if position.quantity > 0:
            # Длинная позиция - продаем
            return await self.order_executor.sell_market(figi, quantity)
        else:
            # Короткая позиция - покупаем
            return await self.order_executor.buy_market(figi, quantity)
    
    async def close_all_positions(self) -> List[OrderResult]:
        """
        Закрывает все открытые позиции по фьючерсам
        
        Returns:
            Список результатов закрытия позиций
        """
        portfolio = await self.get_portfolio()
        results = []
        
        for position in portfolio.positions:
            if position.quantity != 0:
                self.logger.info(f"Закрываем позицию по {position.figi}")
                result = await self.close_position(position.figi)
                results.append(result)
                
                if result.success:
                    self.logger.info(f"Позиция по {position.figi} закрыта успешно")
                else:
                    self.logger.error(f"Ошибка закрытия позиции по {position.figi}: {result.error_message}")
        
        return results
    
    async def get_operations_history(
        self,
        from_date: datetime,
        to_date: datetime,
        figi: Optional[str] = None
    ) -> List[Operation]:
        """
        Получает историю операций по фьючерсам
        
        Args:
            from_date: Дата начала
            to_date: Дата окончания
            figi: FIGI фьючерса (опционально, например, "FUTIMOEXF000")
            
        Returns:
            Список операций
        """
        try:
            return await self._api_client.get_operations_history(from_date, to_date)
            
        except Exception as e:
            self.logger.error(f"Ошибка получения истории операций: {e}")
            return []
    
    async def _process_position_data(self, position_data) -> Optional[Position]:
        """
        Обрабатывает данные позиции по фьючерсам
        
        Args:
            position_data: Данные позиции от API (PortfolioPosition)
            
        Returns:
            Position или None
        """
        try:
            # Получаем данные из PortfolioPosition
            current_price = Money(position_data.current_price).to_float()
            average_price = Money(position_data.average_position_price).to_float()
            quantity = Money(position_data.quantity).to_float()
            
            # Рассчитываем unrealized PnL
            unrealized_pnl = 0.0
            if current_price > 0 and average_price > 0 and quantity != 0:
                unrealized_pnl = (current_price - average_price) * quantity
            
            return Position(
                figi=position_data.figi,
                quantity=int(quantity),
                average_price=average_price,
                current_price=current_price,
                unrealized_pnl=unrealized_pnl,
                realized_pnl=0.0  # Будет рассчитываться из истории операций
            )
            
        except Exception as e:
            self.logger.error(f"Ошибка обработки позиции {position_data.figi}: {e}")
            return None
    
    async def get_guarantee_deposit(self, figi: str) -> float:
        """
        Получает размер гарантийного обеспечения для фьючерса
        
        Args:
            figi: FIGI фьючерса (например, "FUTIMOEXF000")
            
        Returns:
            Размер гарантийного обеспечения в рублях или 0.0 при ошибке
        """
        try:
            margin_info = await self._api_client.get_futures_margin(figi)
            
            if margin_info:
                # Используем initial_margin_on_buy как базовое гарантийное обеспечение
                return margin_info['initial_margin_on_buy']
            
            return 0.0
            
        except Exception as e:
            self.logger.warning(f"Не удалось получить гарантийное обеспечение для {figi}: {e}")
            return 0.0
    
    async def get_point_value(self, figi: str) -> float:
        """
        Получает стоимость одного пункта для фьючерса
        
        Args:
            figi: FIGI фьючерса (например, "FUTIMOEXF000")
            
        Returns:
            Стоимость одного пункта в рублях или 0.0 при ошибке
        """
        try:
            margin_info = await self._api_client.get_futures_margin(figi)
            
            if margin_info:
                min_price_increment = margin_info.get('min_price_increment', 0)
                min_price_increment_amount = margin_info.get('min_price_increment_amount', 0)
                
                if min_price_increment > 0:
                    return min_price_increment_amount / min_price_increment
            
            return 0.0
            
        except Exception as e:
            self.logger.warning(f"Не удалось получить стоимость пункта для {figi}: {e}")
            return 0.0
    
    async def get_contracts_per_lot(self, figi: str) -> int:
        """
        Получает количество контрактов в одном лоте для фьючерса
        
        Args:
            figi: FIGI фьючерса (например, "FUTIMOEXF000")
            
        Returns:
            Количество контрактов в лоте или 0 при ошибке
        """
        try:
            instrument_info = await self._api_client.get_instrument_by_figi(figi)
            
            if instrument_info and hasattr(instrument_info, 'lot'):
                return int(instrument_info.lot)
            
            return 0
            
        except Exception as e:
            self.logger.warning(f"Не удалось получить количество контрактов в лоте для {figi}: {e}")
            return 0
    
    async def get_deposit(self) -> float:
        """
        Получает размер депозита (общая сумма портфеля)
        
        Returns:
            Размер депозита в рублях или 0.0 при ошибке
        """
        try:
            # Получаем портфель напрямую из API
            response = await self._api_client.get_portfolio()
            if not response:
                return 0.0
            
            return Money(response.total_amount_portfolio).to_float()
            
        except Exception as e:
            self.logger.warning(f"Не удалось получить депозит: {e}")
            return 0.0
    
    async def get_portfolio_data(self) -> Dict[str, Any]:
        """
        Получает данные портфеля в виде словаря (для совместимости с тестами)
        
        Returns:
            Словарь с данными портфеля
        """
        portfolio = await self.get_portfolio()
        
        return {
            'total_amount': portfolio.total_amount,
            'blocked_amount': portfolio.blocked_amount,
            'available_amount': portfolio.available_amount,
            'positions': [
                {
                    'figi': pos.figi,
                    'quantity': pos.quantity,
                    'average_price': pos.average_price,
                    'current_price': pos.current_price,
                    'unrealized_pnl': pos.unrealized_pnl,
                    'realized_pnl': pos.realized_pnl
                }
                for pos in portfolio.positions
            ],
            'variation_margin': portfolio.variation_margin,
            'guarantee_deposit': portfolio.guarantee_deposit,
            'pnl': portfolio.pnl,
            'last_update': datetime.now().isoformat()
        }
    
    
    def _is_cache_valid(self) -> bool:
        """
        Проверяет валидность кэша
        
        Returns:
            True если кэш валиден, False иначе
        """
        if self._cache_timestamp is None:
            return False
        
        return (datetime.now() - self._cache_timestamp).total_seconds() < self._cache_ttl
    
    def _build_portfolio_from_cache(self) -> Portfolio:
        """
        Строит портфель из кэша
        
        Returns:
            Portfolio из кэша
        """
        positions = list(self._positions_cache.values())
        
        return Portfolio(
            total_amount=0.0,  # TODO: Кэшировать общую сумму
            blocked_amount=0.0,
            available_amount=0.0,
            positions=positions,
            variation_margin=0.0,
            guarantee_deposit=0.0,
            pnl=0.0
        )


# Пример использования
async def main():
    """Пример использования PortfolioManager"""
    logger = get_logger(__name__)
    config = load_config()
    
    async with TinkoffAPIClient(
        token=config.tcs_client.token,
        account_id=config.tcs_client.id,
        sandbox_token=config.tcs_client.sandbox_token
    ) as api_client:
        
        portfolio_manager = PortfolioManager(api_client)
        
        # Получаем портфель
        portfolio = await portfolio_manager.get_portfolio()
        logger.info(f"Портфель: {portfolio.total_amount:.2f} руб")
        logger.info(f"Доступно: {portfolio.available_amount:.2f} руб")
        logger.info(f"Позиций: {len(portfolio.positions)}")
        
        # Проверяем позицию по фьючерсу
        position = await portfolio_manager.get_position("FUTIMOEXF000")
        if position:
            logger.info(f"Позиция по фьючерсу: {position.quantity} лотов")
        else:
            logger.info("Позиции по фьючерсу нет")


if __name__ == "__main__":
    asyncio.run(main())
