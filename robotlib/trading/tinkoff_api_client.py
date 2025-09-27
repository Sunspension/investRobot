"""
Обертка над Tinkoff AsyncClient для унификации API вызовов
"""
import asyncio
from typing import Optional
import inspect
from tinkoff.invest.clients import Services

from tinkoff.invest import (
    AsyncClient, 
    OrderDirection, 
    OrderType, 
    OrderState
)
from tinkoff.invest.schemas import MoneyValue
from tinkoff.invest.exceptions import InvestError
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
from robotlib.utils.money import money_value_to_float, money_value_to_float_with_currency, float_to_money_value, Money
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
    
    async def _check_market_availability_detailed(self) -> tuple[bool, str, Optional[str]]:
        """Подробная проверка доступности с причиной для логов/ошибок.
        Возвращает пару: (ok, reason), где reason: 'ok' | 'market_closed' | 'client_not_initialized' |
        'account_not_found' | 'api_error'.
        """
        try:
            mode = "sandbox" if self.is_sandbox else "production"
            self._logger.info(f"Проверка доступности рынка (mode={mode}, account_id={self._account_id})")

            # 1) Проверяем торговые часы.
            try:
                is_open = await is_trading_time_with_api()
            except Exception as e:
                self._logger.error(f"Ошибка проверки торговых часов: {e}")
                return False, "api_error", str(e)
            if not is_open:
                self._logger.warning("Рынок закрыт - торговля недоступна")
                return False, "market_closed", None

            # 2) Готовность сервисов
            if not self._services:
                self._logger.error("API services не инициализированы")
                return False, "client_not_initialized", None

            # 3) Проверка аккаунта
            try:
                await self._limiter_get.acquire()
                account_exists = False
                accounts_list: list[str] = []
                parsed_ok = True
                could_verify_account = False

                # Жёстко разделяем режимы: в песочнице не трогаем прод-аккаунты и наоборот
                if mode == "sandbox":
                    # Пытаемся проверить через sandbox API, при ошибке/моках — откатываемся на users.get_accounts
                    tried_sandbox = False
                    if getattr(self._services, 'sandbox', None) and hasattr(self._services.sandbox, 'get_sandbox_accounts'):
                        try:
                            tried_sandbox = True
                            accounts = await self._services.sandbox.get_sandbox_accounts()
                            acc_objs = getattr(accounts, 'accounts', None)
                            try:
                                if isinstance(acc_objs, list):
                                    accounts_list = [str(getattr(acc, 'id', '')) for acc in acc_objs if getattr(acc, 'id', None)]
                                    could_verify_account = True
                                elif acc_objs is not None and hasattr(acc_objs, 'id'):
                                    accounts_list = [str(getattr(acc_objs, 'id', ''))]
                                    could_verify_account = True
                                else:
                                    accounts_list = []
                            except TypeError:
                                accounts_list = []
                                parsed_ok = False
                        except TypeError:
                            # В тестах get_sandbox_accounts может быть Mock (не awaitable)
                            pass
                        except Exception:
                            # Любая иная ошибка — игнорируем и попробуем users.get_accounts
                            pass
                    if (not could_verify_account) and getattr(self._services, 'users', None) and hasattr(self._services.users, 'get_accounts'):
                        accounts = await self._services.users.get_accounts()
                        acc_objs = getattr(accounts, 'accounts', None)
                        try:
                            if isinstance(acc_objs, list):
                                accounts_list = [str(getattr(acc, 'id', '')) for acc in acc_objs if getattr(acc, 'id', None)]
                                could_verify_account = True
                            elif acc_objs is not None and hasattr(acc_objs, 'id'):
                                accounts_list = [str(getattr(acc_objs, 'id', ''))]
                                could_verify_account = True
                            else:
                                accounts_list = []
                        except TypeError:
                            accounts_list = []
                            parsed_ok = False
                    account_exists = any(acc_id == str(self._account_id) for acc_id in accounts_list if acc_id)
                elif mode == "production" and getattr(self._services, 'users', None) and hasattr(self._services.users, 'get_accounts'):
                    accounts = await self._services.users.get_accounts()
                    acc_objs = getattr(accounts, 'accounts', None)
                    try:
                        if isinstance(acc_objs, list):
                            accounts_list = [str(getattr(acc, 'id', '')) for acc in acc_objs if getattr(acc, 'id', None)]
                            could_verify_account = True
                        elif acc_objs is not None and hasattr(acc_objs, 'id'):
                            accounts_list = [str(getattr(acc_objs, 'id', ''))]
                            could_verify_account = True
                        else:
                            accounts_list = []
                    except TypeError:
                        accounts_list = []
                        parsed_ok = False
                    account_exists = any(acc_id == str(self._account_id) for acc_id in accounts_list if acc_id)

                self._logger.info(f"Доступные аккаунты ({mode}): {accounts_list}")
                if not parsed_ok:
                    self._logger.error("Не удалось корректно распарсить список аккаунтов")
                    return False, "api_error", "accounts_parse_error"
                # Если список проверили и нужного ID нет — ошибка
                if could_verify_account and not account_exists:
                    self._logger.error(f"Счет {self._account_id} не найден")
                    return False, "account_not_found", None
                return True, "ok", None
            except Exception as e:
                self._logger.error(f"Ошибка проверки аккаунта: {e}")
                return False, "api_error", str(e)

        except Exception as e:
            self._logger.error(f"Ошибка проверки доступности рынка: {e}")
            return False, "api_error", str(e)

    async def check_market_availability(self) -> bool:
        """
        Проверяет доступность рынка для торговли.
        Совместимая обертка, возвращающая только bool.
        """
        ok, _reason, _detail = await self._check_market_availability_detailed()
        if ok:
            self._logger.info("Рынок доступен для торговли")
        return ok
    
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
            # Проверяем доступность рынка (метод может быть замокан в тестах)
            if not await self.check_market_availability():
                return OrderResult(success=False, error_message="Рынок недоступен для торговли")
            
            # Валидация количества до обращения к API
            if quantity is None or int(quantity) <= 0:
                msg = "Количество лотов должно быть больше 0"
                self._logger.error(msg)
                return OrderResult(success=False, error_message=msg)

            self._logger.info(
                f"Размещение приказа: {direction.name} {quantity} лотов "
                f"{figi} по цене {price or 'рыночная'} (mode={'sandbox' if self.is_sandbox else 'production'}, account_id={self._account_id})"
            )
            
            result = await _place_order(self, figi, direction, quantity, price, order_type)
            if result.success:
                self._logger.info(f"Приказ размещен успешно: {result.order_id}")
            else:
                self._logger.error(result.error_message or "Ошибка размещения")
            return result
                
        except InvestError as e:
            # Преобразуем известные ошибки в понятные сообщения
            raw = str(e)
            friendly = None
            if (
                "Not enough balance" in raw
                or "30034" in raw  # код из Metadata для нехватки баланса/ГО
                or "INVALID_ARGUMENT" in raw
            ):
                friendly = "Недостаточно средств/ГО для размещения приказа"
            elif (
                "quantity" in raw and ("missing" in raw or "equal to 0" in raw)
                or "30015" in raw
            ):
                friendly = "Количество лотов не указано или равно 0"
            elif (
                "Need confirmation" in raw
                or "FAILED_PRECONDITION" in raw
                or "90001" in raw  # типовой код подтверждения
            ):
                friendly = "Требуется подтверждение в приложении (SMS/Push)"
            error_msg = f"Ошибка размещения приказа: {friendly or raw}"
            self._logger.error(error_msg)
            return OrderResult(success=False, error_message=error_msg)
        except Exception as e:
            raw = str(e)
            # Общий фолбэк
            error_msg = f"Ошибка размещения приказа: {raw}"
            self._logger.error(error_msg)
            return OrderResult(success=False, error_message=error_msg)
    
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
        figi: str = None,
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
                    # Получаем point_value для правильной конвертации валюты
                    point_value = 1.0
                    if figi:
                        try:
                            margin_info = await self.get_futures_margin(figi)
                            if margin_info and 'min_price_increment' in margin_info and 'min_price_increment_amount' in margin_info:
                                min_price_increment = margin_info['min_price_increment']
                                min_price_increment_amount = margin_info['min_price_increment_amount']
                                if min_price_increment > 0:
                                    point_value = min_price_increment_amount / min_price_increment
                        except Exception as e:
                            self._logger.warning(f"Не удалось получить point_value для {figi}: {e}")
                            point_value = 10.0  # Значение по умолчанию для фьючерса на MOEX
                    
                    return OrderResult(
                        success=True,
                        order_id=order_id,
                        executed_price=Money(order_state.executed_order_price).to_float_with_currency(point_value),
                        executed_quantity=order_state.lots_executed,
                        commission=Money(order_state.initial_commission).to_float_with_currency(point_value),
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
            return await self.wait_for_order_execution(result.order_id, figi)
        
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
            return await self.wait_for_order_execution(result.order_id, figi)
        
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
    
    
    async def get_operations_by_cursor(self, from_date, to_date, cursor=None, limit=100):
        """Получает историю операций с пагинацией через курсор"""
        try:
            if self._sandbox_token:
                # В sandbox режиме используем обычный метод get_operations
                # так как get_operations_by_cursor не поддерживается
                response = await self._services.sandbox.get_sandbox_operations(
                    account_id=self._account_id,
                    from_=from_date,
                    to=to_date
                )
                return response
            else:
                from tinkoff.invest.schemas import GetOperationsByCursorRequest
                
                request = GetOperationsByCursorRequest(
                    account_id=self._account_id,
                    from_=from_date,
                    to=to_date,
                    cursor=cursor,
                    limit=limit
                )
                
                response = await self._services.operations.get_operations_by_cursor(request)
                return response
            
        except Exception as e:
            self._logger.error(f"Ошибка получения операций с курсором: {e}")
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
            # Сначала пробуем users.get_accounts (для совместимости тестов/моков)
            try:
                res_users = self._services.users.get_accounts()
                return await res_users if inspect.isawaitable(res_users) else res_users
            except Exception:
                # В режиме песочницы пробуем sandbox variant
                if self.is_sandbox:
                    res_sb = self._services.sandbox.get_sandbox_accounts()
                    return await res_sb if inspect.isawaitable(res_sb) else res_sb
                raise
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
