"""
Обертка над Tinkoff AsyncClient для унификации API вызовов
"""
import asyncio
from typing import Optional
from tinkoff.invest.clients import Services

from tinkoff.invest import (
    AsyncClient, 
    OrderDirection, 
    OrderType, 
    OrderState
)
from tinkoff.invest.schemas import MoneyValue
from robotlib.trading.clients.tinkoff.orders_api import (
    OrderResult as _OrderResult,
    place_order as _place_order,
    cancel_order as _orders_cancel,
    get_order_status as _orders_get_status,
)
from robotlib.trading.clients.tinkoff.market_data_api import (
    get_candles as _md_get_candles,
    create_market_data_stream as _md_create_stream,
)
from robotlib.trading.clients.tinkoff.portfolio_api import (
    get_portfolio as _pf_get_portfolio,
    get_positions as _pf_get_positions,
    get_operations_history as _pf_get_operations,
)
from robotlib.trading.clients.tinkoff.instruments_api import (
    get_instrument_by_figi as _ins_get_by_figi,
    get_futures_margin as _ins_get_futures_margin,
)
from robotlib.utils.logger import get_logger
from robotlib.utils.rate_limiter import TokenBucket

from robotlib.utils.market_hours import is_trading_time_with_api
from robotlib.utils.money import money_value_to_float, float_to_money_value
import time


OrderResult = _OrderResult


class TinkoffAPIClient:
    """Обертка над Tinkoff AsyncClient для унификации API вызовов"""
    
    def __init__(
        self, 
        token: str, 
        account_id: str, 
        sandbox_token: Optional[str] = None,
        *,
        rate_limit_get_rps: float = 8.0,
        rate_limit_get_burst: int = 16,
        rate_limit_post_rps: float = 2.0,
        rate_limit_post_burst: int = 4,
    ):
        """
        Инициализация API клиента
        
        Args:
            token: Токен доступа к Tinkoff API
            account_id: ID торгового счета
            sandbox_token: Токен песочницы (если None, используется продакшн)
        """
        self._token = token
        self._account_id = account_id
        self._sandbox_token = sandbox_token
        self._client: Optional[AsyncClient] = None
        self._services = None
        self._logger = get_logger(__name__)
        # Лимитеры запросов
        self._limiter_get = TokenBucket(
            capacity=rate_limit_get_burst, 
            fill_rate_per_sec=rate_limit_get_rps
        )
        self._limiter_post = TokenBucket(
            capacity=rate_limit_post_burst, 
            fill_rate_per_sec=rate_limit_post_rps
        )
        
    # Совместимость: публичные свойства
    @property
    def account_id(self) -> str:
        return self._account_id

    @property
    def token(self) -> str:
        return self._token

    @property
    def sandbox_token(self) -> Optional[str]:
        return self._sandbox_token

    @property
    def client(self) -> Optional[AsyncClient]:
        return self._client

    @property
    def services(self) -> Optional[Services]:
        return self._services

    @client.setter
    def client(self, value: Optional[AsyncClient]) -> None:
        self._client = value

    async def __aenter__(self):
        """Асинхронный контекстный менеджер - вход"""
        self._client = AsyncClient(
            token=self._token,
            sandbox_token=self._sandbox_token
        )
        self._services = await self._client.__aenter__()
        return self
        
    async def __aexit__(
        self, 
        exc_type, 
        exc_val, 
        exc_tb
    ):
        """Асинхронный контекстный менеджер - выход"""
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def check_market_availability(self) -> bool:
        """
        Проверяет доступность рынка для торговли
        
        Returns:
            True если рынок доступен, False иначе
        """
        try:
            # 1) Проверяем торговые часы (асинхронно)
            try:
                is_open = await is_trading_time_with_api()
            except Exception:
                return False
            if not is_open:
                self._logger.warning("Рынок закрыт - торговля недоступна")
                return False

            # 2) Проверяем подключение к API
            if not self._client:
                self._logger.error("Клиент API не инициализирован")
                return False

            # 3) Проверяем доступность счета: users.get_accounts (или sandbox.get_sandbox_accounts как запасной вариант)
            try:
                await self._limiter_get.acquire()
                account_exists = False
                if getattr(self._services, 'users', None) and hasattr(self._services.users, 'get_accounts'):
                    accounts = await self._services.users.get_accounts()
                    account_exists = any(acc.id == self._account_id for acc in getattr(accounts, 'accounts', []))
                elif getattr(self._services, 'sandbox', None) and hasattr(self._services.sandbox, 'get_sandbox_accounts'):
                    accounts = await self._services.sandbox.get_sandbox_accounts()
                    account_exists = any(acc.id == self._account_id for acc in getattr(accounts, 'accounts', []))
                if not account_exists:
                    self._logger.error(f"Счет {self._account_id} не найден")
                    return False
                self._logger.info("Рынок доступен для торговли")
                return True
            except Exception as e:
                self._logger.error(f"Ошибка проверки аккаунта: {e}")
                return False
            
        except Exception as e:
            self._logger.error(f"Ошибка проверки доступности рынка: {e}")
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
            
            self._logger.info(
                f"Размещение приказа: {direction.name} {quantity} лотов "
                f"{figi} по цене {price or 'рыночная'}"
            )
            
            result = await _place_order(self, figi, direction, quantity, price, order_type)
            if result.success:
                self._logger.info(f"Приказ размещен успешно: {result.order_id}")
            else:
                self._logger.error(result.error_message or "Ошибка размещения")
            return result
                
        except Exception as e:
            error_msg = f"Ошибка размещения приказа: {e}"
            self._logger.error(error_msg)
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
            # Используем orders_api
            return await _orders_get_status(self, order_id)
            
        except Exception as e:
            self._logger.error(f"Ошибка получения статуса приказа {order_id}: {e}")
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
                
                # Проверяем статус приказа (учитываем enum)
                status = getattr(order_state, "execution_report_status", None)
                status_name = getattr(status, "name", str(status))
                if status_name == "EXECUTION_REPORT_STATUS_FILL":
                    # Приказ исполнен
                    return OrderResult(
                        success=True,
                        order_id=order_id,
                        executed_price=money_value_to_float(order_state.executed_order_price),
                        executed_quantity=order_state.lots_executed,
                        commission=money_value_to_float(order_state.initial_commission),
                        order_status="FILL",
                        is_executed=True
                    )
                elif status_name == "EXECUTION_REPORT_STATUS_CANCELLED":
                    # Приказ отменен
                    return OrderResult(
                        success=False,
                        order_id=order_id,
                        error_message="Приказ отменен",
                        order_status="CANCELLED",
                        is_executed=False
                    )
                elif status_name == "EXECUTION_REPORT_STATUS_REJECTED":
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
                self._logger.error(f"Ошибка проверки статуса приказа {order_id}: {e}")
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
            ok = await _orders_cancel(self, order_id)
            if ok:
                self._logger.info(f"Приказ {order_id} отменен")
            return ok
            
        except Exception as e:
            self._logger.error(f"Ошибка отмены приказа {order_id}: {e}")
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
            return await _pf_get_portfolio(self)
        except Exception as e:
            self._logger.error(f"Ошибка получения портфеля: {e}")
            return None
    
    async def get_positions(self):
        """Получает позиции"""
        try:
            return await _pf_get_positions(self)
        except Exception as e:
            self._logger.error(f"Ошибка получения позиций: {e}")
            return None
    
    async def get_operations_history(self, from_date, to_date):
        """Получает историю операций"""
        try:
            return await _pf_get_operations(self, from_date, to_date)
        except Exception as e:
            self._logger.error(f"Ошибка получения истории операций: {e}")
            return None
    
    # Методы для работы с инструментами
    async def get_instrument_by_figi(self, figi: str):
        """Получает информацию об инструменте по FIGI"""
        try:
            return await _ins_get_by_figi(self, figi)
        except Exception as e:
            self._logger.error(f"Ошибка получения инструмента {figi}: {e}")
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
            self._logger.info(f"🔍 Запрос свечей: FIGI={figi}, from={from_date}, to={to_date}, interval={interval}")
            self._logger.info(f"🔍 API клиент готов: client={self.client is not None}, services={self._services is not None}")
            
            if not self.client or not self._services:
                self._logger.error("❌ API client не инициализирован")
                return None
                
            response = await _md_get_candles(self, figi, from_date, to_date, interval)
            
            self._logger.info(f"🔍 Получен ответ: {type(response)}")
            if response and hasattr(response, 'candles'):
                self._logger.info(f"🔍 Количество свечей в ответе: {len(response.candles)}")
            else:
                self._logger.warning(f"🔍 Ответ не содержит свечей: {response}")
                
            return response
        except Exception as e:
            self._logger.error(f"Ошибка получения свечей {figi}: {e}")
            return None
    
    async def create_market_data_stream(self):
        """Создает стрим рыночных данных"""
        try:
            return _md_create_stream(self)
        except Exception as e:
            self._logger.error(f"Ошибка создания стрима рыночных данных: {e}")
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
            return await _ins_get_futures_margin(self, figi)
            
        except Exception as e:
            self._logger.error(f"Ошибка получения маржи для {figi}: {e}")
            return None
    
    
    # Методы для работы с аккаунтами
    async def get_accounts(self):
        """Получает список аккаунтов"""
        try:
            await self._limiter_get.acquire()
            return await self._services.users.get_accounts()
        except Exception as e:
            self._logger.error(f"Ошибка получения аккаунтов: {e}")
            return None
    
    async def get_user_info(self):
        """Получает информацию о пользователе"""
        try:
            await self._limiter_get.acquire()
            return await self._services.users.get_info()
        except Exception as e:
            self._logger.error(f"Ошибка получения информации о пользователе: {e}")
            return None
    
    # Совместимость: конвертеры денег
    def _float_to_money_value(self, value: float) -> MoneyValue:
        """Конвертирует float в MoneyValue (совместимость со старыми тестами)."""
        return float_to_money_value(value, currency="rub")

    def _money_value_to_float(self, money_value: MoneyValue) -> float:
        """Конвертирует MoneyValue в float (совместимость со старыми тестами)."""
        return money_value_to_float(money_value)

    @property
    def is_sandbox(self) -> bool:
        """Проверяет, используется ли песочница"""
        return self._sandbox_token is not None

    async def sandbox_pay_in(self, amount_rub: float) -> bool:
        """Пополнение sandbox-счёта в рублях.
        Возвращает True при успехе. В продакшне недоступно.
        """
        try:
            if not self.is_sandbox:
                self._logger.warning("sandbox_pay_in: не песочница")
                return False
            amount = MoneyValue(currency="rub", units=int(amount_rub), nano=int((amount_rub - int(amount_rub)) * 1_000_000_000))
            await self._services.sandbox.sandbox_pay_in(account_id=self._account_id, amount=amount)
            self._logger.info(f"Sandbox пополнен на {amount_rub} RUB")
            return True
        except Exception as e:
            self._logger.error(f"Ошибка sandbox_pay_in: {e}")
            return False
