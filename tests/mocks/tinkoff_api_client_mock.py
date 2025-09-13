"""
Мок для TinkoffAPIClient - полная реализация интерфейса
"""
from typing import Any, Optional
from robotlib.trading.order_executor import OrderResult

class MockTinkoffAPIClient:
    """Мок для TinkoffAPIClient - полная реализация интерфейса"""
    
    def __init__(self, token: str = "mock_token", account_id: str = "mock_account", sandbox_token: str = None, **kwargs):
        self.token = token
        self.account_id = account_id
        self.sandbox_token = sandbox_token
        self._connected = False
        self._success_rate = kwargs.get('success_rate', 1.0)
        self._orders = []
        self._order_counter = 0
        
        # Мок данные
        self._mock_portfolio = {
            'total_amount_shares': {'units': 100000, 'nano': 0},
            'total_amount_bonds': {'units': 0, 'nano': 0},
            'total_amount_etf': {'units': 0, 'nano': 0},
            'total_amount_currencies': {'units': 0, 'nano': 0},
            'total_amount_futures': {'units': 0, 'nano': 0},
            'expected_yield': {'units': 0, 'nano': 0}
        }
        
        self._mock_positions = []
        self._mock_operations = []
        self._mock_instruments = {}
        self._mock_candles = []
        self._mock_accounts = [{'id': account_id, 'name': 'Mock Account', 'type': 'ACCOUNT_TYPE_TINKOFF'}]
        self._mock_user_info = {'prem_status': False, 'qual_status': False, 'tariff': 'INVESTOR'}
    
    async def __aenter__(self):
        self._connected = True
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._connected = False
    
    async def check_market_availability(self) -> bool:
        """Проверяет доступность рынка"""
        return True
    
    async def place_order(
        self,
        figi: str,
        quantity: int,
        price: Optional[float] = None,
        direction: str = "buy",
        order_type: str = "market",
        order_id: Optional[str] = None
    ) -> OrderResult:
        """Размещает ордер"""
        self._order_counter += 1
        order_id = order_id or f"mock_order_{self._order_counter}"
        success = self._success_rate >= 1.0
        
        self._orders.append({
            'order_id': order_id,
            'figi': figi,
            'quantity': quantity,
            'price': price,
            'direction': direction,
            'order_type': order_type,
            'status': 'NEW_STATUS' if success else 'REJECTED'
        })
        
        return OrderResult(
            success=success,
            order_id=order_id,
            error_message=None if success else "Mock order rejected",
            executed_price=price or 100.0,
            executed_quantity=quantity if success else 0,
            commission=0.01,
            order_status='NEW_STATUS' if success else 'REJECTED',
            is_executed=success
        )
    
    async def get_order_status(self, order_id: str) -> Optional[Any]:
        """Получает статус ордера"""
        for order in self._orders:
            if order['order_id'] == order_id:
                from unittest.mock import Mock
                return Mock(order_id=order_id, status=order['status'])
        return None
    
    async def wait_for_order_execution(
        self, 
        order_id: str, 
        timeout: int = 30, 
        check_interval: float = 1.0
    ) -> OrderResult:
        """Ожидает исполнения ордера"""
        # В моке сразу возвращаем успешное исполнение
        return OrderResult(
            success=True,
            order_id=order_id,
            executed_price=100.0,
            executed_quantity=1,
            commission=0.01,
            order_status='FILL',
            is_executed=True
        )
    
    async def cancel_order(self, order_id: str) -> bool:
        """Отменяет ордер"""
        for order in self._orders:
            if order['order_id'] == order_id:
                order['status'] = 'CANCELLED'
                return True
        return False
    
    async def buy_market(self, figi: str, quantity: int, wait_execution: bool = True) -> OrderResult:
        """Покупка по рыночной цене"""
        return await self.place_order(figi, quantity, direction="buy", order_type="market")
    
    async def sell_market(self, figi: str, quantity: int, wait_execution: bool = True) -> OrderResult:
        """Продажа по рыночной цене"""
        return await self.place_order(figi, quantity, direction="sell", order_type="market")
    
    async def buy_limit(self, figi: str, quantity: int, price: float) -> OrderResult:
        """Покупка по лимитной цене"""
        return await self.place_order(figi, quantity, price, direction="buy", order_type="limit")
    
    async def sell_limit(self, figi: str, quantity: int, price: float) -> OrderResult:
        """Продажа по лимитной цене"""
        return await self.place_order(figi, quantity, price, direction="sell", order_type="limit")
    
    async def get_portfolio(self) -> Any:
        """Получает портфель"""
        from unittest.mock import Mock
        portfolio = Mock()
        for key, value in self._mock_portfolio.items():
            setattr(portfolio, key, Mock(**value) if isinstance(value, dict) else value)
        return portfolio
    
    async def get_positions(self) -> Any:
        """Получает позиции"""
        from unittest.mock import Mock
        return Mock(positions=self._mock_positions)
    
    async def get_operations_history(self, from_date, to_date) -> Any:
        """Получает историю операций"""
        from unittest.mock import Mock
        return Mock(operations=self._mock_operations)
    
    async def get_instrument_by_figi(self, figi: str) -> Any:
        """Получает информацию об инструменте по FIGI"""
        if figi not in self._mock_instruments:
            from unittest.mock import Mock
            self._mock_instruments[figi] = Mock(
                figi=figi,
                ticker="MOCK",
                name="Mock Instrument",
                instrument_type="INSTRUMENT_TYPE_FUTURES",
                lot=10  # Количество контрактов в лоте
            )
        return self._mock_instruments[figi]
    
    async def get_candles(self, figi: str, from_date, to_date, interval) -> Any:
        """Получает свечи"""
        from unittest.mock import Mock
        return Mock(candles=self._mock_candles)
    
    async def create_market_data_stream(self) -> Any:
        """Создает стрим рыночных данных"""
        from unittest.mock import Mock
        return Mock()
    
    async def get_futures_margin(self, figi: str) -> Optional[dict]:
        """Получает информацию о гарантийном обеспечении для фьючерса"""
        return {
            'initial_margin': {'units': 1000, 'nano': 0},
            'min_price_increment': {'units': 1, 'nano': 0},
            'min_quantity': 1
        }
    
    async def get_accounts(self) -> Any:
        """Получает список аккаунтов"""
        from unittest.mock import Mock
        return Mock(accounts=self._mock_accounts)
    
    async def get_user_info(self) -> Any:
        """Получает информацию о пользователе"""
        from unittest.mock import Mock
        return Mock(**self._mock_user_info)
    
    def is_sandbox(self) -> bool:
        """Проверяет, используется ли песочница"""
        return self.sandbox_token is not None
    
    async def get_candles(self, figi: str, from_date, to_date, interval: int = 1) -> Any:
        """Генерирует мок-свечи для демонстрации"""
        from datetime import datetime, timedelta
        from tinkoff.invest import Candle, Quotation
        import random
        
        # Генерируем свечи за последние 2 часа
        candles = []
        current_time = datetime.now()
        base_price = 2900.0
        
        for i in range(120):  # 120 свечей по 1 минуте = 2 часа
            candle_time = current_time - timedelta(minutes=120-i)
            
            # Генерируем реалистичные цены
            price_change = random.uniform(-5, 5)
            open_price = base_price + price_change
            high_price = open_price + random.uniform(0, 3)
            low_price = open_price - random.uniform(0, 3)
            close_price = open_price + random.uniform(-2, 2)
            volume = random.randint(100, 1000)
            
            # Обновляем базовую цену для следующей свечи
            base_price = close_price
            
            candle = Candle(
                figi=figi,
                interval=interval,
                open=Quotation(units=int(open_price), nano=int((open_price - int(open_price)) * 1_000_000_000)),
                high=Quotation(units=int(high_price), nano=int((high_price - int(high_price)) * 1_000_000_000)),
                low=Quotation(units=int(low_price), nano=int((low_price - int(low_price)) * 1_000_000_000)),
                close=Quotation(units=int(close_price), nano=int((close_price - int(close_price)) * 1_000_000_000)),
                volume=volume,
                time=candle_time
            )
            candles.append(candle)
        
        # Создаем мок-ответ
        from unittest.mock import Mock
        return Mock(candles=candles)