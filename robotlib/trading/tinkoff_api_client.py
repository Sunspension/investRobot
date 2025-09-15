"""
Обертка над Tinkoff AsyncClient для унификации API вызовов
"""
import asyncio

from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from tinkoff.invest import (
    AsyncClient, 
    OrderDirection, 
    OrderType, 
    PostOrderRequest,
    GetOrdersRequest,
    CancelOrderRequest,
    OrderState,
    GetFuturesMarginRequest
)
from tinkoff.invest.schemas import MoneyValue
from robotlib.utils.logger import get_logger

from robotlib.utils.market_hours import check_market_open
from robotlib.utils.money import Money
from config_data.config import load_config
import time


@dataclass
class OrderResult:
    """Результат выполнения приказа"""
    success: bool
    order_id: Optional[str] = None
    error_message: Optional[str] = None
    executed_price: Optional[float] = None
    executed_quantity: Optional[int] = None
    commission: Optional[float] = None
    order_status: Optional[str] = None  # NEW_STATUS, FILL, CANCELLED, REJECTED
    is_executed: bool = False  # True если приказ полностью исполнен


class TinkoffAPIClient:
    """Обертка над Tinkoff AsyncClient для унификации API вызовов"""
    
    def __init__(
        self, 
        token: str, 
        account_id: str, 
        sandbox_token: Optional[str] = None
    ):
        """
        Инициализация API клиента
        
        Args:
            token: Токен доступа к Tinkoff API
            account_id: ID торгового счета
            sandbox_token: Токен песочницы (если None, используется продакшн)
        """
        self.token = token
        self.account_id = account_id
        self.sandbox_token = sandbox_token
        self.client: Optional[AsyncClient] = None
        self.services = None
        self.logger = get_logger(__name__)
        
    async def __aenter__(self):
        """Асинхронный контекстный менеджер - вход"""
        self.client = AsyncClient(
            token=self.token,
            sandbox_token=self.sandbox_token
        )
        self.services = await self.client.__aenter__()
        return self
        
    async def __aexit__(
        self, 
        exc_type, 
        exc_val, 
        exc_tb
    ):
        """Асинхронный контекстный менеджер - выход"""
        if self.client:
            await self.client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def check_market_availability(self) -> bool:
        """
        Проверяет доступность рынка для торговли
        
        Returns:
            True если рынок доступен, False иначе
        """
        try:
            # Проверяем торговые часы
            if not check_market_open():
                self.logger.warning("Рынок закрыт - торговля недоступна")
                return False
            
            # Проверяем подключение к API
            if not self.client:
                self.logger.error("Клиент API не инициализирован")
                return False
            
            # Проверяем доступность счета
            accounts = await self.services.users.get_accounts()
            account_exists = any(acc.id == self.account_id for acc in accounts.accounts)
            
            if not account_exists:
                self.logger.error(f"Счет {self.account_id} не найден")
                return False
            
            self.logger.info("Рынок доступен для торговли")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка проверки доступности рынка: {e}")
            return False
    
    async def place_order(
        self,
        figi: str,
        direction: OrderDirection,
        quantity: int,
        price: Optional[float] = None,
        order_type: OrderType = OrderType.ORDER_TYPE_MARKET
    ) -> OrderResult:
        """
        Размещает торговый приказ
        
        Args:
            figi: FIGI инструмента
            direction: Направление приказа (покупка/продажа)
            quantity: Количество лотов
            price: Цена (для лимитных приказов)
            order_type: Тип приказа (рыночный/лимитный)
            
        Returns:
            OrderResult с результатом выполнения
        """
        try:
            # Проверяем доступность рынка
            if not await self.check_market_availability():
                return OrderResult(
                    success=False,
                    error_message="Рынок недоступен для торговли"
                )
            
            # Подготавливаем запрос
            request = PostOrderRequest(
                figi=figi,
                quantity=quantity,
                price=self._float_to_money_value(price) if price else None,
                direction=direction,
                account_id=self.account_id,
                order_type=order_type,
                order_id=str(int(datetime.now().timestamp() * 1000))  # Уникальный ID
            )
            
            self.logger.info(
                f"Размещение приказа: {direction.name} {quantity} лотов "
                f"{figi} по цене {price or 'рыночная'}"
            )
            
            # Отправляем приказ
            if self.sandbox_token:
                response = await self.services.sandbox.post_sandbox_order(
                    figi=figi,
                    quantity=quantity,
                    price=self._float_to_money_value(price) if price else None,
                    direction=direction,
                    account_id=self.account_id,
                    order_type=order_type,
                    order_id=str(int(datetime.now().timestamp() * 1000))
                )
            else:
                response = await self.services.orders.post_order(request)
            
            if response.order_id:
                self.logger.info(f"Приказ размещен успешно: {response.order_id}")
                return OrderResult(
                    success=True,
                    order_id=response.order_id,
                    executed_price=price,
                    executed_quantity=quantity
                )
            else:
                self.logger.error("Не удалось получить ID приказа")
                return OrderResult(
                    success=False,
                    error_message="Не удалось получить ID приказа"
                )
                
        except Exception as e:
            error_msg = f"Ошибка размещения приказа: {e}"
            self.logger.error(error_msg)
            return OrderResult(
                success=False,
                error_message=error_msg
            )
    
    async def get_order_status(self, order_id: str) -> Optional[OrderState]:
        """
        Получает статус приказа
        
        Args:
            order_id: ID приказа
            
        Returns:
            OrderState или None если приказ не найден
        """
        try:
            if self.sandbox_token:
                response = await self.services.sandbox.get_sandbox_orders(account_id=self.account_id)
            else:
                request = GetOrdersRequest(account_id=self.account_id)
                response = await self.services.orders.get_orders(request)
            
            for order in response.orders:
                if order.order_id == order_id:
                    return order
            
            return None
            
        except Exception as e:
            self.logger.error(f"Ошибка получения статуса приказа {order_id}: {e}")
            return None
    
    async def wait_for_order_execution(
        self, 
        order_id: str, 
        max_wait_time: int = 30,
        check_interval: float = 1.0
    ) -> OrderResult:
        """
        Ожидает исполнения приказа
        
        Args:
            order_id: ID приказа
            max_wait_time: Максимальное время ожидания в секундах
            check_interval: Интервал проверки в секундах
            
        Returns:
            OrderResult с обновленным статусом
        """
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            try:
                order_state = await self.get_order_status(order_id)
                
                if not order_state:
                    await asyncio.sleep(check_interval)
                    continue
                
                # Проверяем статус приказа
                if order_state.execution_report_status == "EXECUTION_REPORT_STATUS_FILL":
                    # Приказ исполнен
                    return OrderResult(
                        success=True,
                        order_id=order_id,
                        executed_price=self._money_value_to_float(order_state.executed_order_price),
                        executed_quantity=order_state.lots_executed,
                        commission=self._money_value_to_float(order_state.initial_commission),
                        order_status="FILL",
                        is_executed=True
                    )
                elif order_state.execution_report_status == "EXECUTION_REPORT_STATUS_CANCELLED":
                    # Приказ отменен
                    return OrderResult(
                        success=False,
                        order_id=order_id,
                        error_message="Приказ отменен",
                        order_status="CANCELLED",
                        is_executed=False
                    )
                elif order_state.execution_report_status == "EXECUTION_REPORT_STATUS_REJECTED":
                    # Приказ отклонен
                    return OrderResult(
                        success=False,
                        order_id=order_id,
                        error_message="Приказ отклонен",
                        order_status="REJECTED",
                        is_executed=False
                    )
                else:
                    # Приказ еще в процессе (NEW_STATUS, PARTIALLY_FILL)
                    await asyncio.sleep(check_interval)
                    continue
                    
            except Exception as e:
                self.logger.error(f"Ошибка проверки статуса приказа {order_id}: {e}")
                await asyncio.sleep(check_interval)
                continue
        
        # Таймаут - приказ не исполнился за отведенное время
        return OrderResult(
            success=False,
            order_id=order_id,
            error_message=f"Таймаут ожидания исполнения приказа (>{max_wait_time}с)",
            order_status="TIMEOUT",
            is_executed=False
        )
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Отменяет приказ
        
        Args:
            order_id: ID приказа для отмены
            
        Returns:
            True если приказ отменен успешно, False иначе
        """
        try:
            request = CancelOrderRequest(
                account_id=self.account_id,
                order_id=order_id
            )
            
            if self.sandbox_token:
                await self.services.sandbox.cancel_sandbox_order(
                    account_id=self.account_id,
                    order_id=order_id
                )
            else:
                await self.services.orders.cancel_order(request)
            self.logger.info(f"Приказ {order_id} отменен")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка отмены приказа {order_id}: {e}")
            return False
    
    # Удобные методы для торговли
    async def buy_market(self, figi: str, quantity: int, wait_execution: bool = True) -> OrderResult:
        """Покупка по рыночной цене"""
        result = await self.place_order(
            figi=figi,
            direction=OrderDirection.ORDER_DIRECTION_BUY,
            quantity=quantity,
            order_type=OrderType.ORDER_TYPE_MARKET
        )
        
        # Если приказ размещен успешно и нужно ждать исполнения
        if result.success and result.order_id and wait_execution:
            return await self.wait_for_order_execution(result.order_id)
        
        return result
    
    async def sell_market(self, figi: str, quantity: int, wait_execution: bool = True) -> OrderResult:
        """Продажа по рыночной цене"""
        result = await self.place_order(
            figi=figi,
            direction=OrderDirection.ORDER_DIRECTION_SELL,
            quantity=quantity,
            order_type=OrderType.ORDER_TYPE_MARKET
        )
        
        # Если приказ размещен успешно и нужно ждать исполнения
        if result.success and result.order_id and wait_execution:
            return await self.wait_for_order_execution(result.order_id)
        
        return result
    
    async def buy_limit(self, figi: str, quantity: int, price: float) -> OrderResult:
        """Покупка по лимитной цене"""
        return await self.place_order(
            figi=figi,
            direction=OrderDirection.ORDER_DIRECTION_BUY,
            quantity=quantity,
            price=price,
            order_type=OrderType.ORDER_TYPE_LIMIT
        )
    
    async def sell_limit(self, figi: str, quantity: int, price: float) -> OrderResult:
        """Продажа по лимитной цене"""
        return await self.place_order(
            figi=figi,
            direction=OrderDirection.ORDER_DIRECTION_SELL,
            quantity=quantity,
            price=price,
            order_type=OrderType.ORDER_TYPE_LIMIT
        )
    
    # Методы для работы с портфелем
    async def get_portfolio(self):
        """Получает портфель"""
        try:
            if self.sandbox_token:
                return await self.services.sandbox.get_sandbox_portfolio(account_id=self.account_id)
            else:
                return await self.services.operations.get_portfolio(account_id=self.account_id)
        except Exception as e:
            self.logger.error(f"Ошибка получения портфеля: {e}")
            return None
    
    async def get_positions(self):
        """Получает позиции"""
        try:
            if self.sandbox_token:
                return await self.services.sandbox.get_sandbox_positions(account_id=self.account_id)
            else:
                return await self.services.operations.get_positions(account_id=self.account_id)
        except Exception as e:
            self.logger.error(f"Ошибка получения позиций: {e}")
            return None
    
    async def get_operations_history(self, from_date, to_date):
        """Получает историю операций"""
        try:
            if self.sandbox_token:
                return await self.services.sandbox.get_sandbox_operations(
                    account_id=self.account_id,
                    from_=from_date,
                    to=to_date
                )
            else:
                return await self.services.operations.get_operations(
                    account_id=self.account_id,
                    from_=from_date,
                    to=to_date
                )
        except Exception as e:
            self.logger.error(f"Ошибка получения истории операций: {e}")
            return None
    
    # Методы для работы с инструментами
    async def get_instrument_by_figi(self, figi: str):
        """Получает информацию об инструменте по FIGI"""
        try:
            return await self.services.instruments.get_instrument_by(figi=figi)
        except Exception as e:
            self.logger.error(f"Ошибка получения инструмента {figi}: {e}")
            return None
    
    async def get_candles(
        self, 
        figi: str, 
        from_date, 
        to_date, 
        interval
    ):
        """Получает свечи"""
        try:
            self.logger.info(f"🔍 Запрос свечей: FIGI={figi}, from={from_date}, to={to_date}, interval={interval}")
            self.logger.info(f"🔍 API client ready: {self.client is not None}, services: {self.services is not None}")
            
            if not self.client or not self.services:
                self.logger.error("❌ API client не инициализирован")
                return None
                
            response = await self.services.market_data.get_candles(
                figi=figi,
                from_=from_date,
                to=to_date,
                interval=interval
            )
            
            self.logger.info(f"🔍 Получен ответ: {type(response)}")
            if response and hasattr(response, 'candles'):
                self.logger.info(f"🔍 Количество свечей в ответе: {len(response.candles)}")
            else:
                self.logger.warning(f"🔍 Ответ не содержит свечей: {response}")
                
            return response
        except Exception as e:
            self.logger.error(f"Ошибка получения свечей {figi}: {e}")
            return None
    
    async def create_market_data_stream(self):
        """Создает стрим рыночных данных"""
        try:
            return self.services.create_market_data_stream()
        except Exception as e:
            self.logger.error(f"Ошибка создания стрима рыночных данных: {e}")
            # Не возвращаем None - это ошибка на уровне сборки
            raise RuntimeError(f"Не удалось создать стрим рыночных данных: {e}")
    
    async def get_futures_margin(self, figi: str) -> Optional[dict]:
        """
        Получает информацию о гарантийном обеспечении для фьючерса
        
        Args:
            figi: FIGI фьючерса (например, "FUTIMOEXF000")
            
        Returns:
            Словарь с информацией о марже или None при ошибке
        """
        try:
            response = await self.services.instruments.get_futures_margin(
                figi=figi
            )
            
            return {
                'initial_margin_on_buy': Money(response.initial_margin_on_buy).to_float(),
                'initial_margin_on_sell': Money(response.initial_margin_on_sell).to_float(),
                'min_price_increment': Money(response.min_price_increment).to_float(),
                'min_price_increment_amount': Money(response.min_price_increment_amount).to_float()
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка получения маржи для {figi}: {e}")
            return None
    
    
    # Методы для работы с аккаунтами
    async def get_accounts(self):
        """Получает список аккаунтов"""
        try:
            return await self.services.users.get_accounts()
        except Exception as e:
            self.logger.error(f"Ошибка получения аккаунтов: {e}")
            return None
    
    async def get_user_info(self):
        """Получает информацию о пользователе"""
        try:
            return await self.services.users.get_info()
        except Exception as e:
            self.logger.error(f"Ошибка получения информации о пользователе: {e}")
            return None
    
    # Вспомогательные методы
    def _float_to_money_value(self, value: float) -> MoneyValue:
        """Конвертирует float в MoneyValue"""
        return MoneyValue(
            currency="rub",
            units=int(value),
            nano=int((value - int(value)) * 1_000_000_000)
        )
    
    def _money_value_to_float(self, money_value: MoneyValue) -> float:
        """Конвертирует MoneyValue в float"""
        if not money_value:
            return 0.0
        return money_value.units + money_value.nano / 1_000_000_000
    
    @property
    def is_sandbox(self) -> bool:
        """Проверяет, используется ли песочница"""
        return self.sandbox_token is not None

    async def sandbox_pay_in(self, amount_rub: float) -> bool:
        """Пополнение sandbox-счёта в рублях.
        Возвращает True при успехе. В продакшне недоступно.
        """
        try:
            if not self.is_sandbox:
                self.logger.warning("sandbox_pay_in: не песочница")
                return False
            amount = MoneyValue(currency="rub", units=int(amount_rub), nano=int((amount_rub - int(amount_rub)) * 1_000_000_000))
            await self.services.sandbox.sandbox_pay_in(account_id=self.account_id, amount=amount)
            self.logger.info(f"Sandbox пополнен на {amount_rub} RUB")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка sandbox_pay_in: {e}")
            return False


# Пример использования
async def main():
    """Пример использования TinkoffAPIClient"""
    logger = get_logger(__name__)
    config = load_config()
    
    async with TinkoffAPIClient(
        token=config.tcs_client.token,
        account_id=config.tcs_client.id,
        sandbox_token=config.tcs_client.sandbox_token
    ) as api_client:
        
        # Проверяем доступность рынка
        if await api_client.check_market_availability():
            logger.info("Рынок доступен для торговли")
            
            # Пример покупки
            result = await api_client.buy_market(
                figi="FUTIMOEXF000",
                quantity=1
            )
            
            if result.success:
                logger.info(f"Покупка выполнена: {result.order_id}")
            else:
                logger.error(f"Ошибка покупки: {result.error_message}")
        else:
            logger.warning("Рынок недоступен")


if __name__ == "__main__":
    asyncio.run(main())
