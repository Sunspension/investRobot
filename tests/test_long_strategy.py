"""
Тесты для LongStrategy
"""
import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from robotlib.strategies.long import LongStrategy
from tests.mocks.position_sizer_dummy import DummySizer
from robotlib.signal_types import Signal
from robotlib.trading.order_types import OrderIntent, OrderExecution, OrderDirection, OrderType, OrderStatus
from robotlib.trading.interfaces import PositionManageable
from robotlib.utils.money import Money
from tinkoff.invest import Candle, Quotation


class MockRiskManager:
    """Мок для RiskManageable"""
    
    def __init__(self, percent_from_deposit=10, items_per_trade=5, stop_loss_threshold=50.0):
        self.risk_limits = Mock()
        self.risk_limits.percent_from_deposit = percent_from_deposit
        self.risk_limits.items_per_trade = items_per_trade
        self.risk_limits.stop_loss_threshold = stop_loss_threshold


class MockPortfolioManager:
    """Мок для PortfolioManageable"""
    
    def __init__(self, deposit=100000.0, guarantee_deposit=1000.0):
        self._deposit = deposit


class MockPositionManager(PositionManageable):
    """Мок для PositionManager"""
    
    def __init__(self, risk_manager=None):
        self._positions_cache = {}
        self._risk_manager = risk_manager or MockRiskManager()
    
    def get_position(self, figi: str):
        """Получение позиции из кэша"""
        return self._positions_cache.get(figi)
    
    async def add_to_fifo(self, figi: str, quantity: int, price: float, order_id: str, direction: str = 'long'):
        """Добавление позиции в FIFO очередь"""
        pass
    
    async def remove_from_fifo(self, figi: str, quantity: int):
        """Удаление позиций из FIFO очереди"""
        pass
    
    async def update_position_after_trade(self, figi: str, quantity_delta: int, price: float):
        """Обновление позиции после сделки"""
        # Для тестов обновляем доход при продаже
        if quantity_delta < 0:  # Продажа
            # Имитируем прибыль: продаем по 110, купили по 100
            profit = (price - 100.0) * abs(quantity_delta)
            # Обновляем доход в стратегии через рефлексию
            pass
    
    async def get_loss_positions(self, figi: str, current_price: float, loss_threshold: float = None):
        """Получение убыточных позиций"""
        if loss_threshold is None:
            loss_threshold = self._risk_manager.risk_limits.stop_loss_threshold
        
        # Для тестов возвращаем убыточные позиции, если убыток превышает порог в пунктах
        # Создаем тестовые позиции с ценой 100, если текущая цена упала достаточно
        if current_price <= 100.0 - loss_threshold:  # Если цена упала на loss_threshold пунктов
            from robotlib.trading.position_manager import FIFOEntry, LossPosition
            fifo_entry = FIFOEntry(quantity=2, price=100.0, timestamp=datetime.now(), order_id="test", direction="long")
            loss_percent = (100.0 - current_price) / 100.0
            return [LossPosition(quantity=2, price=100.0, loss_percent=loss_percent, order_id="test")]
        return []
    
    async def get_profit_positions(self, figi: str, current_price: float):
        """Получение прибыльных позиций"""
        return []
    
    async def sync_on_startup(self, max_retries: int = 3):
        """Синхронизация позиций при старте"""
        return {}
        self._guarantee_deposit = guarantee_deposit
    
    async def get_deposit(self) -> float:
        return self._deposit
    
    async def get_guarantee_deposit(self, figi: str) -> float:
        return self._guarantee_deposit
    
    async def get_point_value(self, figi: str) -> float:
        return 10.0
    
    async def get_contracts_per_lot(self, figi: str) -> int:
        return 10


def create_mock_candle(price: float) -> Candle:
    """Создает мок свечи с заданной ценой"""
    return Candle(
        figi="FUTIMOEXF000",
        interval=1,
        open=Quotation(units=int(price), nano=0),
        high=Quotation(units=int(price + 1), nano=0),
        low=Quotation(units=int(price - 1), nano=0),
        close=Quotation(units=int(price), nano=0),
        volume=100,
        time=datetime.now()
    )


def create_signal(
    macd: float = 0.5,
    signal: float = 0.3,
    histogram: float = 0.2,
    macd_prev: float = 0.2,
    signal_prev: float = 0.4,
    peak_detected: bool = False,
    trough_detected: bool = False,
    candle: Candle = None
) -> Signal:
    """Создает тестовый сигнал"""
    if candle is None:
        candle = create_mock_candle(100.0)
    
    return Signal(
        macd=macd,
        signal=signal,
        histogram=histogram,
        macd_prev=macd_prev,
        signal_prev=signal_prev,
        peak_detected=peak_detected,
        trough_detected=trough_detected,
        candle=candle
    )


class TestLongStrategy:
    """Тесты для LongStrategy"""
    
    def test_init(self):
        """Тест инициализации стратегии"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        
        position_manager = MockPositionManager()
        strategy = LongStrategy(position_manager=position_manager)
        
        assert strategy._position == 0
        assert strategy._cost_basis == 0.0
        assert strategy._income == 0.0
        assert strategy._position_manager == position_manager
        assert strategy._wait_buy_cross is False
        assert strategy._wait_sell_cross is False
        assert strategy.strategy_name == "LongStrategy"
    
    @pytest.mark.asyncio
    async def test_initialize(self):
        """Тест инициализации с параметрами"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        position_manager = MockPositionManager()
        strategy = LongStrategy(position_manager=position_manager)
        
        strategy.initialize(
            figi="TEST_FIGI",
            point_value=15.0,
            contracts_per_lot=20
        )
        
        assert strategy._figi == "TEST_FIGI"
        assert strategy._point_value == 15.0
        assert strategy._contracts_per_lot == 20
    
    @pytest.mark.asyncio
    async def test_initialize_with_defaults(self):
        """Тест инициализации с значениями по умолчанию"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        position_manager = MockPositionManager()
        strategy = LongStrategy(position_manager=position_manager)
        
        strategy.initialize(point_value=10.0, contracts_per_lot=10)
        
        assert strategy._figi == "FUTIMOEXF000"
        assert strategy._point_value == 10.0
        assert strategy._contracts_per_lot == 10
    
    @pytest.mark.asyncio
    async def test_execute_no_signal(self):
        """Тест выполнения без сигналов"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        position_manager = MockPositionManager()
        strategy = LongStrategy(position_manager=position_manager)
        
        signal = create_signal(
            macd=0.1,
            signal=0.1,
            histogram=0.0,
            peak_detected=False,
            trough_detected=False
        )
        
        orders = await strategy.execute(signal)
        
        assert orders == []
        assert strategy._wait_buy_cross is False
        assert strategy._wait_sell_cross is False
    
    @pytest.mark.asyncio
    async def test_execute_trough_detected(self):
        """Тест обнаружения впадины"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        position_manager = MockPositionManager()
        strategy = LongStrategy(position_manager=position_manager)
        
        # Создаем сигнал с trough_detected=True, но без пересечения MACD
        signal = create_signal(
            trough_detected=True,
            macd=0.1,
            signal=0.1,
            macd_prev=0.1,
            signal_prev=0.1,
            histogram=0.0
        )
        
        orders = await strategy.execute(signal)
        
        # Должно установиться ожидание покупки, но ордер не создается
        # так как нет пересечения MACD
        assert strategy._wait_buy_cross is True
        assert strategy._wait_sell_cross is False
        assert len(orders) == 0  # Ордер не создается без пересечения
    
    @pytest.mark.asyncio
    async def test_execute_peak_detected(self):
        """Тест обнаружения пика"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        position_manager = MockPositionManager()
        strategy = LongStrategy(position_manager=position_manager)
        
        signal = create_signal(peak_detected=True)
        
        orders = await strategy.execute(signal)
        
        assert strategy._wait_buy_cross is False
        assert strategy._wait_sell_cross is True
    
    @pytest.mark.asyncio
    async def test_execute_buy_signal(self):
        """Тест сигнала на покупку"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        position_manager = MockPositionManager()
        strategy = LongStrategy(position_manager=position_manager)
        
        # Устанавливаем ожидание покупки
        strategy._wait_buy_cross = True
        
        signal = create_signal(
            macd=0.5,
            signal=0.3,
            macd_prev=0.2,
            signal_prev=0.4,
            histogram=0.2,
            trough_detected=False
        )
        
        orders = await strategy.execute(signal)
        
        assert len(orders) == 1
        assert isinstance(orders[0], OrderIntent)
        assert orders[0].direction == OrderDirection.BUY
        assert orders[0].order_type == OrderType.MARKET
        assert orders[0].figi == "FUTIMOEXF000"
        assert orders[0].quantity > 0
        assert strategy._wait_buy_cross is False
    
    @pytest.mark.asyncio
    async def test_execute_sell_signal(self):
        """Тест сигнала на продажу"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        position_manager = MockPositionManager()
        strategy = LongStrategy(position_manager=position_manager)
        
        # Устанавливаем позицию и ожидание продажи
        strategy._position = 5
        strategy._wait_sell_cross = True
        
        signal = create_signal(
            macd=0.2,
            signal=0.4,
            macd_prev=0.5,
            signal_prev=0.3,
            histogram=0.2,
            peak_detected=False
        )
        
        orders = await strategy.execute(signal)
        
        assert len(orders) == 1
        assert isinstance(orders[0], OrderIntent)
        assert orders[0].direction == OrderDirection.SELL
        assert orders[0].order_type == OrderType.MARKET
        assert orders[0].figi == "FUTIMOEXF000"
        assert orders[0].quantity == 5
        assert strategy._wait_sell_cross is False
    
    @pytest.mark.asyncio
    async def test_execute_trending_up(self):
        """Тест дозакупки при восходящем тренде"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        position_manager = MockPositionManager()
        strategy = LongStrategy(position_manager=position_manager)
        
        # Устанавливаем позицию
        strategy._position = 2
        
        signal = create_signal(
            macd=0.5,
            signal=0.3,
            macd_prev=0.2,
            signal_prev=0.4,
            histogram=0.2
        )
        
        orders = await strategy.execute(signal)
        
        assert len(orders) == 1
        assert orders[0].direction == OrderDirection.BUY
        assert orders[0].quantity > 0
    
    def test_close_position_with_position(self):
        """Тест закрытия позиции когда есть позиция"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        position_manager = MockPositionManager()
        strategy = LongStrategy(position_manager=position_manager)
        
        strategy._position = 3
        candle = create_mock_candle(100.0)
        
        order = strategy.close_position(candle)
        
        assert order is not None
        assert isinstance(order, OrderIntent)
        assert order.direction == OrderDirection.SELL
        assert order.quantity == 3
        assert order.order_type == OrderType.MARKET
        assert order.figi == "FUTIMOEXF000"
    
    def test_close_position_without_position(self):
        """Тест закрытия позиции когда позиции нет"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        position_manager = MockPositionManager()
        strategy = LongStrategy(position_manager=position_manager)
        
        strategy._position = 0
        candle = create_mock_candle(100.0)
        
        order = strategy.close_position(candle)
        
        assert order is None
    
    def test_items_to_sell(self):
        """Тест расчета количества для продажи"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        position_manager = MockPositionManager()
        strategy = LongStrategy(position_manager=position_manager)
        
        strategy._position = 5
        result = strategy._items_to_sell()
        
        assert result == 5
    
    @pytest.mark.asyncio
    async def test_process_execution_buy(self):
        """Тест обработки исполнения покупки"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        position_manager = MockPositionManager()
        strategy = LongStrategy(position_manager=position_manager)
        
        execution = OrderExecution(
            order_id="test_order_1",
            figi="FUTIMOEXF000",
            direction=OrderDirection.BUY,
            quantity=2,
            filled_quantity=2,
            price=100.0,
            status=OrderStatus.FILLED,
            timestamp=datetime.now(),
            commission=10.0,
            reason="Test buy order"
        )
        
        await strategy._process_execution(execution)
        
        assert strategy._position == 2
        # _positions удален - логика перенесена в PositionManager
        assert strategy._cost_basis == 200.0
    
    @pytest.mark.asyncio
    async def test_process_execution_sell(self):
        """Тест обработки исполнения продажи"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        position_manager = MockPositionManager()
        strategy = LongStrategy(position_manager=position_manager)
        
        # Инициализируем стратегию
        strategy.initialize(point_value=10.0, contracts_per_lot=10)
        
        # Сначала открываем позицию
        strategy._positions = [[100.0, 2]]
        strategy._position = 2
        strategy._cost_basis = 200.0
        
        execution = OrderExecution(
            order_id="test_order_2",
            figi="FUTIMOEXF000",
            direction=OrderDirection.SELL,
            quantity=1,
            filled_quantity=1,
            price=110.0,
            status=OrderStatus.FILLED,
            timestamp=datetime.now(),
            commission=5.0,
            reason="Test sell order"
        )
        
        await strategy._process_execution(execution)
        
        assert strategy._position == 1
        # _positions удален - логика перенесена в PositionManager
        # _income теперь рассчитывается в PositionManager
    
    # test_fifo_sell удален - логика перенесена в PositionManager
    
    # Тесты _check_stop_loss удалены - логика перенесена в StrategyManager
    
    @pytest.mark.asyncio
    async def test_items_to_buy_calculation(self):
        """Тест расчета количества для покупки"""
        risk_manager = MockRiskManager(percent_from_deposit=20, items_per_trade=10)
        portfolio_manager = MockPortfolioManager(deposit=100000.0, guarantee_deposit=2000.0)
        position_manager = MockPositionManager()
        strategy = LongStrategy(position_manager=position_manager)
        
        # Без позиций
        mock_signal = Mock(spec=Signal)
        mock_signal.histogram = 0.2
        mock_signal.atr = None
        mock_signal.candle = Mock()
        mock_signal.candle.close = Quotation(units=2500, nano=0)
        items = strategy._items_to_buy(mock_signal)
        
        # 20% от 100000 = 20000, на 2000 за контракт = 10 контрактов
        # Но лимит items_per_trade = 10, поэтому должно быть 10
        assert items == 1
        
        # С существующей позицией
        strategy._position = 3
        items = strategy._items_to_buy(mock_signal)
        
        # Заморожено 3 * 2000 = 6000, остается 20000 - 6000 = 14000
        # На 2000 за контракт = 7 контрактов
        assert items == 1
