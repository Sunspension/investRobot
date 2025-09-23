"""
Модуль для управления рисками в торговле
"""

from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from robotlib.trading.portfolio_manager import PortfolioManager, Position
from robotlib.utils.money import Money
from robotlib.utils.logger import get_logger
from config_data.config import load_config
from robotlib.trading.tinkoff_api_client import TinkoffAPIClient
import asyncio


class RiskLevel(Enum):
    """Уровни риска"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskLimits:
    """Лимиты риска"""
    # Глобальные лимиты (защита от системных рисков)
    max_daily_loss: float        # Максимальная дневная потеря в рублях
    max_position_size: float     # Максимальный размер позиции в рублях
    
    # Параметры стратегий (торговая логика)
    percent_from_deposit: float = 50.0    # Процент от депозита для торговли
    items_per_trade: int = 20             # Максимальное количество лотов за сделку
    stop_loss_threshold: float = 8.0      # Стоп-лосс в пунктах


@dataclass
class RiskCheck:
    """Результат проверки риска"""
    passed: bool
    risk_level: RiskLevel
    message: str
    recommendation: Optional[str] = None


class RiskManager:
    """Класс для управления рисками"""
    
    def __init__(
        self,
        portfolio_manager: PortfolioManager,
        risk_limits: RiskLimits
    ):
        """
        Инициализация менеджера рисков
        
        Args:
            portfolio_manager: Менеджер портфеля
            risk_limits: Лимиты риска
        """
        self.portfolio_manager = portfolio_manager
        self._risk_limits = risk_limits
        self._logger = get_logger(__name__)
        
        # История убытков
        self._daily_losses: Dict[str, float] = {}
        self._trade_history: List[Dict] = []
    
    @property
    def risk_limits(self) -> RiskLimits:
        """Возвращает лимиты рисков"""
        return self._risk_limits
    
    async def check_trade_risk(
        self,
        figi: str,
        quantity: int,
        price: float,
        direction: str
    ) -> RiskCheck:
        """
        Проверяет риск торговой операции
        
        Args:
            figi: FIGI инструмента
            quantity: Количество лотов
            price: Цена
            direction: Направление ("buy" или "sell")
            
        Returns:
            RiskCheck с результатом проверки
        """
        try:
            trade_value = quantity * price
            portfolio = await self.portfolio_manager.get_portfolio()
            
            # Проверка 1: Максимальное количество лотов за сделку
            if quantity > self._risk_limits.items_per_trade:
                return RiskCheck(
                    passed=False,
                    risk_level=RiskLevel.CRITICAL,
                    message=f"Количество лотов {quantity} превышает лимит {self._risk_limits.items_per_trade}",
                    recommendation="Уменьшите количество лотов"
                )
            
            # Проверка 2: Максимальный размер позиции
            current_position = await self.portfolio_manager.get_position(figi)
            if current_position:
                new_position_value = abs(current_position.quantity + quantity) * price
                if new_position_value > self._risk_limits.max_position_size:
                    return RiskCheck(
                        passed=False,
                        risk_level=RiskLevel.HIGH,
                        message=f"Размер позиции {new_position_value:.2f} руб превышает лимит {self._risk_limits.max_position_size:.2f} руб",
                        recommendation="Уменьшите размер позиции"
                    )
            
            # Проверка 3: Достаточно средств для покупки
            if direction == "buy":
                if not await self.portfolio_manager.can_buy(figi, quantity, price):
                    return RiskCheck(
                        passed=False,
                        risk_level=RiskLevel.HIGH,
                        message="Недостаточно средств для покупки",
                        recommendation="Пополните счет или уменьшите размер сделки"
                    )
            
            # Проверка 4: Достаточно лотов для продажи
            if direction == "sell":
                if not await self.portfolio_manager.can_sell(figi, quantity):
                    return RiskCheck(
                        passed=False,
                        risk_level=RiskLevel.HIGH,
                        message="Недостаточно лотов для продажи",
                        recommendation="Проверьте размер позиции"
                    )
            
            # Проверка 5: Дневные убытки
            daily_loss = await self._get_daily_loss()
            if daily_loss > self._risk_limits.max_daily_loss:
                return RiskCheck(
                    passed=False,
                    risk_level=RiskLevel.CRITICAL,
                    message=f"Дневные убытки {daily_loss:.2f} руб превышают лимит {self._risk_limits.max_daily_loss:.2f} руб",
                    recommendation="Прекратите торговлю на сегодня"
                )
            
            # Проверка 6: Процент от депозита
            current_deposit = await self.portfolio_manager.get_deposit()
            money_limit = current_deposit * (self._risk_limits.percent_from_deposit / 100)
            if trade_value > money_limit:
                return RiskCheck(
                    passed=False,
                    risk_level=RiskLevel.HIGH,
                    message=f"Размер сделки {trade_value:.2f} руб превышает лимит {money_limit:.2f} руб ({self._risk_limits.percent_from_deposit}% от депозита)",
                    recommendation="Уменьшите размер сделки или увеличьте лимит"
                )
            
            # Все проверки пройдены
            risk_level = self._calculate_trade_risk_level(trade_value, portfolio)
            
            return RiskCheck(
                passed=True,
                risk_level=risk_level,
                message="Риски в пределах нормы",
                recommendation="Операция разрешена"
            )
            
        except Exception as e:
            self._logger.error(f"Ошибка проверки риска: {e}")
            return RiskCheck(
                passed=False,
                risk_level=RiskLevel.CRITICAL,
                message=f"Ошибка проверки риска: {e}",
                recommendation="Проверьте настройки"
            )
    
    async def check_stop_loss(self, figi: str) -> Optional[RiskCheck]:
        """
        Проверяет необходимость срабатывания стоп-лосса
        
        Args:
            figi: FIGI инструмента
            
        Returns:
            RiskCheck или None если стоп-лосс не сработал
        """
        try:
            position = await self.portfolio_manager.get_position(figi)
            if not position or position.quantity == 0:
                return None
            
            # Рассчитываем убыток в пунктах
            if position.average_price > 0:
                loss_points = position.average_price - position.current_price
                
                if loss_points >= self._risk_limits.stop_loss_threshold:
                    return RiskCheck(
                        passed=False,
                        risk_level=RiskLevel.CRITICAL,
                        message=f"Стоп-лосс сработал: убыток {loss_points:.2f} пунктов",
                        recommendation="Немедленно закройте позицию"
                    )
            
            return None
            
        except Exception as e:
            self._logger.error(f"Ошибка проверки стоп-лосса: {e}")
            return None
    
    
    async def get_risk_report(self) -> Dict:
        """
        Получает отчет о рисках
        
        Returns:
            Словарь с информацией о рисках
        """
        try:
            portfolio = await self.portfolio_manager.get_portfolio()
            daily_loss = await self._get_daily_loss()
            
            # Анализ позиций
            risky_positions = []
            for position in portfolio.positions:
                if position.quantity != 0:
                    position_risk = await self._calculate_position_risk(position)
                    if position_risk > 0.1:  # Риск больше 10%
                        risky_positions.append({
                            'figi': position.figi,
                            'risk': position_risk,
                            'quantity': position.quantity,
                            'unrealized_pnl': position.unrealized_pnl
                        })
            
            return {
                'portfolio_value': portfolio.total_amount,
                'available_funds': portfolio.available_amount,
                'daily_loss': daily_loss,
                'risky_positions': risky_positions,
                'risk_limits': {
                    'max_daily_loss': self._risk_limits.max_daily_loss,
                    'max_position_size': self._risk_limits.max_position_size,
                    'percent_from_deposit': self._risk_limits.percent_from_deposit,
                    'items_per_trade': self._risk_limits.items_per_trade,
                    'stop_loss_threshold': self._risk_limits.stop_loss_threshold
                },
                'recommendations': await self._get_risk_recommendations()
            }
            
        except Exception as e:
            self._logger.error(f"Ошибка получения отчета о рисках: {e}")
            return {}
    
    async def _get_daily_loss(self) -> float:
        """
        Получает дневные убытки
        
        Returns:
            Сумма дневных убытков в рублях
        """
        try:
            today = datetime.now().date()
            today_str = today.strftime('%Y-%m-%d')
            
            if today_str in self._daily_losses:
                return self._daily_losses[today_str]
            
            # Получаем операции за сегодня
            start_of_day = datetime.combine(today, datetime.min.time())
            end_of_day = datetime.combine(today, datetime.max.time())
            
            operations = await self.portfolio_manager.get_operations_history(
                start_of_day, end_of_day
            )
            
            daily_loss = 0.0
            for operation in operations:
                try:
                    payment = getattr(operation, 'payment', 0)
                    # Приводим MoneyValue/Quotation к float
                    payment_float = Money(payment).to_float()
                except Exception:
                    # Фолбэк: если тип неожиданный, пробуем напрямую
                    try:
                        payment_float = float(payment) if payment is not None else 0.0
                    except Exception:
                        payment_float = 0.0

                if payment_float < 0:  # Убыточная операция
                    daily_loss += abs(payment_float)
            
            self._daily_losses[today_str] = daily_loss
            return daily_loss
            
        except Exception as e:
            self._logger.error(f"Ошибка расчета дневных убытков: {e}")
            return 0.0
    
    
    async def _calculate_position_risk(self, position: Position) -> float:
        """
        Рассчитывает риск позиции
        
        Args:
            position: Позиция
            
        Returns:
            Риск позиции в процентах
        """
        try:
            if position.quantity == 0:
                return 0.0
            
            position_value = abs(position.quantity) * position.current_price
            portfolio = await self.portfolio_manager.get_portfolio()
            
            if portfolio.total_amount == 0:
                return 0.0
            
            return (position_value / portfolio.total_amount) * 100
            
        except Exception as e:
            self._logger.error(f"Ошибка расчета риска позиции: {e}")
            return 0.0
    
    def _calculate_trade_risk_level(
        self, 
        trade_value: float, 
        portfolio
    ) -> RiskLevel:
        """
        Рассчитывает уровень риска сделки
        
        Args:
            trade_value: Стоимость сделки
            portfolio: Портфель
            
        Returns:
            Уровень риска
        """
        if portfolio.total_amount == 0:
            return RiskLevel.CRITICAL
        
        trade_percent = (trade_value / portfolio.total_amount) * 100
        
        if trade_percent < 1:
            return RiskLevel.LOW
        elif trade_percent < 5:
            return RiskLevel.MEDIUM
        elif trade_percent < 10:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL
    
    async def _get_risk_recommendations(self) -> List[str]:
        """
        Получает рекомендации по управлению рисками
        
        Returns:
            Список рекомендаций
        """
        recommendations = []
        
        try:
            portfolio = await self.portfolio_manager.get_portfolio()
            daily_loss = await self._get_daily_loss()
            
            # Рекомендации по дневным убыткам
            if daily_loss > self._risk_limits.max_daily_loss * 0.8:
                recommendations.append("Приближаетесь к лимиту дневных убытков")
            
            # Рекомендации по концентрации
            if len(portfolio.positions) > 0:
                max_position_risk = max(
                    await self._calculate_position_risk(pos) 
                    for pos in portfolio.positions 
                    if pos.quantity != 0
                )
                
                if max_position_risk > 20:
                    recommendations.append("Высокая концентрация в одной позиции")
            
            # Рекомендации по стоп-лоссам
            for position in portfolio.positions:
                if position.quantity != 0:
                    stop_loss_check = await self.check_stop_loss(position.figi)
                    if stop_loss_check and not stop_loss_check.passed:
                        recommendations.append(f"Стоп-лосс по {position.figi}: {stop_loss_check.message}")
            
        except Exception as e:
            self._logger.error(f"Ошибка получения рекомендаций: {e}")
        
        return recommendations


# Пример использования
async def main():
    """Пример использования RiskManager"""
    logger = get_logger(__name__)
    config = load_config()
    
    # Настройки риска
    risk_limits = RiskLimits(
        max_position_size=100000,  # 100k руб
        max_daily_loss=5000,       # 5k руб
        max_portfolio_risk=20,     # 20%
        max_single_trade=10000,    # 10k руб
        stop_loss_percent=5,       # 5%
        take_profit_percent=10     # 10%
    )
    
    async with TinkoffAPIClient(
        token=config.tcs_client.token,
        account_id=config.tcs_client.account_id,
        sandbox_token=config.tcs_client.sandbox_token
    ) as api_client:
        
        portfolio_manager = PortfolioManager(api_client)
        risk_manager = RiskManager(portfolio_manager, risk_limits)
        
        # Проверяем риск сделки
        risk_check = await risk_manager.check_trade_risk(
            figi="FUTIMOEXF000",
            quantity=1,
            price=2500.0,
            direction="buy"
        )
        
        logger.info(f"Проверка риска: {risk_check.passed}")
        logger.info(f"Уровень риска: {risk_check.risk_level.value}")
        logger.info(f"Сообщение: {risk_check.message}")
        
        # Получаем отчет о рисках
        risk_report = await risk_manager.get_risk_report()
        logger.info(f"Отчет о рисках: {risk_report}")


if __name__ == "__main__":
    asyncio.run(main())
