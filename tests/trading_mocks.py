"""
Моки для тестирования торговых компонентов
"""
from unittest.mock import Mock, AsyncMock
from typing import List, Dict, Any, Optional
from datetime import datetime

from robotlib.trading.interfaces import (
    APIClientable, 
    OrderExecutable, 
    SignalManageable,
    MarketDataStreamable,
    TinkoffAPIClientable
)
from robotlib.trading.order_executor import OrderResult
from robotlib.trading.portfolio_manager import Portfolio, Position
from robotlib.trading.risk_manager import RiskLimits, RiskCheck
from robotlib.signal_types import Signal
from robotlib.trading.order_types import OrderIntent, OrderExecution, OrderDirection, OrderType, OrderStatus
from tests.mocks import MockRiskManager, MockPortfolioManager, MockTradingDependencies
from datetime import datetime
import uuid


class MockAPIClient:
    """Мок для API клиента"""
    
    def __init__(self, **kwargs):
        self._connected = False
    
    async def __aenter__(self):
        self._connected = True
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._connected = False


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
        portfolio = Mock()
        for key, value in self._mock_portfolio.items():
            setattr(portfolio, key, Mock(**value) if isinstance(value, dict) else value)
        return portfolio
    
    async def get_positions(self) -> Any:
        """Получает позиции"""
        return Mock(positions=self._mock_positions)
    
    async def get_operations_history(self, from_date, to_date) -> Any:
        """Получает историю операций"""
        return Mock(operations=self._mock_operations)
    
    async def get_instrument_by_figi(self, figi: str) -> Any:
        """Получает информацию об инструменте по FIGI"""
        if figi not in self._mock_instruments:
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
        return Mock(candles=self._mock_candles)
    
    async def create_market_data_stream(self) -> Any:
        """Создает стрим рыночных данных"""
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
        return Mock(accounts=self._mock_accounts)
    
    async def get_user_info(self) -> Any:
        """Получает информацию о пользователе"""
        return Mock(**self._mock_user_info)
    
    def is_sandbox(self) -> bool:
        """Проверяет, используется ли песочница"""
        return self.sandbox_token is not None


class MockOrderExecutor:
    """Мок для исполнителя ордеров - симулирует исполнение ордеров на исторических данных"""
    
    def __init__(self, **kwargs):
        self._orders = []
        self._success_rate = kwargs.get('success_rate', 1.0)  # 100% успеха по умолчанию
        self._mock_prices = kwargs.get('mock_prices', {})  # Мок цены для разных FIGI
        self._executions = []  # Список исполненных ордеров
        self._commission_rate = kwargs.get('commission_rate', 0.01)  # 1% комиссия
    
    async def execute_order(self, order_intent: OrderIntent) -> OrderExecution:
        """
        Симулирует исполнение OrderIntent на исторических данных
        """
        # Генерируем уникальный ID для ордера
        order_id = str(uuid.uuid4())
        
        # Получаем цену исполнения (используем цену из свечи или мок цену)
        if order_intent.figi in self._mock_prices:
            executed_price = self._mock_prices[order_intent.figi]
        else:
            # Для тестирования используем фиксированную цену
            executed_price = 1500.0  # Базовая цена для фьючерса
        
        # Симулируем успешное исполнение
        success = self._success_rate >= 1.0
        
        if success:
            executed_quantity = order_intent.quantity
            status = OrderStatus.FILLED
        else:
            executed_quantity = 0
            status = OrderStatus.REJECTED
        
        # Рассчитываем комиссию
        commission = executed_price * executed_quantity * self._commission_rate
        
        # Создаем OrderExecution
        execution = OrderExecution(
            order_id=order_id,
            intent=order_intent,
            executed_price=executed_price,
            executed_quantity=executed_quantity,
            executed_at=datetime.now(),
            status=status,
            commission=commission
        )
        
        # Сохраняем исполнение для анализа
        self._executions.append(execution)
        
        return execution
    
    async def buy_market(self, figi: str, quantity: int, wait_execution: bool = True) -> OrderResult:
        """Мок покупки по рыночной цене"""
        success = self._success_rate >= 1.0
        self._orders.append(('buy', figi, quantity))
        
        return OrderResult(
            success=success,
            order_id=f"mock_buy_{len(self._orders)}",
            error_message=None if success else "Mock error",
            executed_price=100.0 if success else None,
            executed_quantity=quantity if success else 0,
            order_status="FILL" if success else "REJECTED",
            is_executed=success
        )
    
    async def sell_market(self, figi: str, quantity: int, wait_execution: bool = True) -> OrderResult:
        """Мок продажи по рыночной цене"""
        success = self._success_rate >= 1.0
        self._orders.append(('sell', figi, quantity))
        
        return OrderResult(
            success=success,
            order_id=f"mock_sell_{len(self._orders)}",
            error_message=None if success else "Mock error",
            executed_price=105.0 if success else None,
            executed_quantity=quantity if success else 0,
            order_status="FILL" if success else "REJECTED",
            is_executed=success
        )
    
    async def buy_limit(self, figi: str, quantity: int, price: float) -> OrderResult:
        """Мок покупки по лимитной цене"""
        success = self._success_rate >= 1.0
        self._orders.append(('buy_limit', figi, quantity, price))
        
        return OrderResult(
            success=success,
            order_id=f"mock_buy_limit_{len(self._orders)}",
            error_message=None if success else "Mock error"
        )
    
    async def sell_limit(self, figi: str, quantity: int, price: float) -> OrderResult:
        """Мок продажи по лимитной цене"""
        success = self._success_rate >= 1.0
        self._orders.append(('sell_limit', figi, quantity, price))
        
        return OrderResult(
            success=success,
            order_id=f"mock_sell_limit_{len(self._orders)}",
            error_message=None if success else "Mock error"
        )


class MockSignalManager:
    """Мок для менеджера сигналов"""
    
    def __init__(self, **kwargs):
        self._candles = []
        self._signals_enabled = kwargs.get('signals_enabled', True)
        self._signal_frequency = kwargs.get('signal_frequency', 0.3)  # 30% вероятность сигнала
    
    def add_candle(self, candle) -> Optional[Signal]:
        """Мок добавления свечи"""
        # Сохраняем свечу
        candle_data = {
            'date': candle.time,
            'open': getattr(candle, 'open', 100.0),
            'high': getattr(candle, 'high', 105.0),
            'low': getattr(candle, 'low', 95.0),
            'close': getattr(candle, 'close', 100.0),
            'macd': 0.1,
            'signal': 0.05,
            'histogram': 0.05
        }
        self._candles.append(candle_data)
        
        # Иногда возвращаем сигнал
        if self._signals_enabled and len(self._candles) % 3 == 0:
            return Signal(
                trough_detected=True,
                peak_detected=False,
                histogram=0.1,
                macd=0.15,
                signal=0.1,
                macd_prev=0.05,
                signal_prev=0.08,
                candle=candle
            )
        
        return None
    
    @property
    def candles(self) -> List[Dict[str, Any]]:
        """Возвращает список свечей"""
        return self._candles


class MockMarketDataStream:
    """Мок для потока рыночных данных"""
    
    def __init__(self, **kwargs):
        self._callbacks = []
        self._running = False
        self._candles = kwargs.get('candles', [])
    
    def add_signal_callback(self, callback) -> None:
        """Добавляет колбэк для обработки сигналов"""
        self._callbacks.append(callback)
    
    async def start(self) -> None:
        """Запускает поток данных"""
        self._running = True
        # В реальном тесте здесь можно симулировать получение данных
    
    async def stop(self) -> None:
        """Останавливает поток данных"""
        self._running = False


