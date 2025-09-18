"""
Тесты для ShortStrategy
"""
import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from robotlib.strategies.short import ShortStrategy
from robotlib.signal_types import Signal
from robotlib.trading.order_types import OrderIntent, OrderExecution, OrderDirection, OrderType, OrderStatus
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


class TestShortStrategy:
    """Тесты для ShortStrategy"""
    
    def test_init(self):
        """Тест инициализации стратегии"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        
        strategy = ShortStrategy(risk_manager, portfolio_manager)
        
        assert strategy._position == 0
        assert strategy._cost_basis == 0.0
        assert strategy._income == 0.0
        assert strategy._positions == []
        assert strategy._wait_short_sell_cross is False
        assert strategy._wait_short_buy_cross is False
        assert strategy.strategy_name == "ShortStrategy"
    
    @pytest.mark.asyncio
    async def test_initialize(self):
        """Тест инициализации с параметрами"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        strategy = ShortStrategy(risk_manager, portfolio_manager)
        
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
        strategy = ShortStrategy(risk_manager, portfolio_manager)
        
        strategy.initialize(point_value=10.0, contracts_per_lot=10)
        
        assert strategy._figi == "FUTIMOEXF000"
        assert strategy._point_value == 10.0
        assert strategy._contracts_per_lot == 10
    
    @pytest.mark.asyncio
    async def test_execute_no_signal(self):
        """Тест выполнения без сигналов"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        strategy = ShortStrategy(risk_manager, portfolio_manager)
        
        signal = create_signal(
            macd=0.1,
            signal=0.1,
            histogram=0.0,
            peak_detected=False,
            trough_detected=False
        )
        
        orders = await strategy.execute(signal)
        
        assert orders == []
        assert strategy._wait_short_sell_cross is False
        assert strategy._wait_short_buy_cross is False
    
    @pytest.mark.asyncio
    async def test_execute_peak_detected(self):
        """Тест обнаружения пика (сигнал на шорт)"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        strategy = ShortStrategy(risk_manager, portfolio_manager)
        
        signal = create_signal(peak_detected=True)
        
        orders = await strategy.execute(signal)
        
        assert strategy._wait_short_sell_cross is True
        assert strategy._wait_short_buy_cross is False
    
    @pytest.mark.asyncio
    async def test_execute_trough_detected(self):
        """Тест обнаружения впадины (сигнал на закрытие шорта)"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        strategy = ShortStrategy(risk_manager, portfolio_manager)
        
        signal = create_signal(trough_detected=True)
        
        orders = await strategy.execute(signal)
        
        assert strategy._wait_short_sell_cross is False
        assert strategy._wait_short_buy_cross is True
    
    @pytest.mark.asyncio
    async def test_execute_short_sell_signal(self):
        """Тест сигнала на открытие шорта"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        strategy = ShortStrategy(risk_manager, portfolio_manager)
        
        # Устанавливаем ожидание открытия шорта
        strategy._wait_short_sell_cross = True
        
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
        assert orders[0].quantity > 0
        assert strategy._wait_short_sell_cross is False
    
    @pytest.mark.asyncio
    async def test_execute_short_buy_signal(self):
        """Тест сигнала на закрытие шорта"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        strategy = ShortStrategy(risk_manager, portfolio_manager)
        
        # Устанавливаем позицию и ожидание закрытия шорта
        strategy._position = 5
        strategy._wait_short_buy_cross = True
        
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
        assert orders[0].quantity == 5
        assert strategy._wait_short_buy_cross is False
    
    @pytest.mark.asyncio
    async def test_execute_trending_down(self):
        """Тест дозакупки при нисходящем тренде"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        strategy = ShortStrategy(risk_manager, portfolio_manager)
        
        # Устанавливаем позицию
        strategy._position = 2
        
        signal = create_signal(
            macd=0.2,
            signal=0.4,
            macd_prev=0.5,
            signal_prev=0.3,
            histogram=0.2
        )
        
        orders = await strategy.execute(signal)
        
        assert len(orders) == 1
        assert orders[0].direction == OrderDirection.SELL
        assert orders[0].quantity > 0
    
    def test_close_position_with_position(self):
        """Тест закрытия позиции когда есть позиция"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        strategy = ShortStrategy(risk_manager, portfolio_manager)
        
        strategy._position = 3
        candle = create_mock_candle(100.0)
        
        order = strategy.close_position(candle)
        
        assert order is not None
        assert isinstance(order, OrderIntent)
        assert order.direction == OrderDirection.BUY  # Покрываем шорт
        assert order.quantity == 3
        assert order.order_type == OrderType.MARKET
        assert order.figi == "FUTIMOEXF000"
    
    def test_close_position_without_position(self):
        """Тест закрытия позиции когда позиции нет"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        strategy = ShortStrategy(risk_manager, portfolio_manager)
        
        strategy._position = 0
        candle = create_mock_candle(100.0)
        
        order = strategy.close_position(candle)
        
        assert order is None
    
    def test_items_to_buy_short(self):
        """Тест расчета количества для закрытия шорта"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        strategy = ShortStrategy(risk_manager, portfolio_manager)
        
        strategy._position = 5
        result = strategy._items_to_buy_short()
        
        assert result == 5
    
    def test_process_execution_sell(self):
        """Тест обработки исполнения продажи (открытие шорта)"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        strategy = ShortStrategy(risk_manager, portfolio_manager)
        
        execution = OrderExecution(
            order_id="test_order_1",
            figi="FUTIMOEXF000",
            direction=OrderDirection.SELL,
            quantity=2,
            filled_quantity=2,
            price=100.0,
            status=OrderStatus.FILLED,
            timestamp=datetime.now(),
            commission=10.0,
            reason="Test short sell order"
        )
        
        strategy._process_execution(execution)
        
        assert strategy._position == 2
        assert len(strategy._positions) == 1
        assert strategy._positions[0] == [100.0, 2]
        assert strategy._cost_basis == 200.0
    
    @pytest.mark.asyncio
    async def test_process_execution_buy(self):
        """Тест обработки исполнения покупки (закрытие шорта)"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        strategy = ShortStrategy(risk_manager, portfolio_manager)
        
        # Инициализируем стратегию
        strategy.initialize(point_value=10.0, contracts_per_lot=10)
        
        # Сначала открываем шорт
        strategy._positions = [[100.0, 2]]
        strategy._position = 2
        strategy._cost_basis = 200.0
        
        execution = OrderExecution(
            order_id="test_order_2",
            figi="FUTIMOEXF000",
            direction=OrderDirection.BUY,
            quantity=1,
            filled_quantity=1,
            price=90.0,  # Покрываем по более низкой цене
            status=OrderStatus.FILLED,
            timestamp=datetime.now(),
            commission=5.0,
            reason="Test short cover order"
        )
        
        strategy._process_execution(execution)
        
        assert strategy._position == 1
        assert len(strategy._positions) == 1
        assert strategy._positions[0] == [100.0, 1]
        assert strategy._income > 0  # Должна быть прибыль (продали по 100, купили по 90)
    
    @pytest.mark.asyncio
    async def test_fifo_buy_short(self):
        """Тест FIFO покупки для закрытия шорта"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager()
        strategy = ShortStrategy(risk_manager, portfolio_manager)
        
        # Инициализируем стратегию
        strategy.initialize(point_value=10.0, contracts_per_lot=10)
        
        positions = [[100.0, 2], [105.0, 3]]
        price = 90.0  # Покрываем по более низкой цене
        qty_to_buy = 3
        commission = 10.0
        
        new_positions, profit, new_pos = strategy._fifo_buy_short(
            positions, price, qty_to_buy, commission
        )
        
        assert len(new_positions) == 1
        assert new_positions[0] == [105.0, 2]  # Остался один лот
        assert new_pos == 2
        assert profit > 0  # Должна быть прибыль (продали по 100, купили по 90)
    
    def test_check_stop_loss_no_loss(self):
        """Тест проверки стоп-лосса без убытка"""
        risk_manager = MockRiskManager(stop_loss_threshold=50.0)
        portfolio_manager = MockPortfolioManager()
        strategy = ShortStrategy(risk_manager, portfolio_manager)
        
        # Позиция с небольшой потерей
        strategy._positions = [[100.0, 2]]
        candle = create_mock_candle(105.0)  # Потеря 5 пунктов для шорта
        
        orders = strategy._check_stop_loss(candle)
        
        assert orders == []
    
    def test_check_stop_loss_with_loss(self):
        """Тест проверки стоп-лосса с убытком"""
        risk_manager = MockRiskManager(stop_loss_threshold=50.0)
        portfolio_manager = MockPortfolioManager()
        strategy = ShortStrategy(risk_manager, portfolio_manager)
        
        # Позиция с большой потерей
        strategy._positions = [[100.0, 2]]
        candle = create_mock_candle(160.0)  # Потеря 60 пунктов для шорта
        
        orders = strategy._check_stop_loss(candle)
        
        assert len(orders) == 1
        assert orders[0].direction == OrderDirection.BUY  # Покрываем шорт
        assert orders[0].quantity == 2
        assert orders[0].order_type == OrderType.MARKET
    
    @pytest.mark.asyncio
    async def test_items_to_sell_short_calculation(self):
        """Тест расчета количества для открытия шорта"""
        risk_manager = MockRiskManager(percent_from_deposit=20, items_per_trade=10)
        portfolio_manager = MockPortfolioManager(deposit=100000.0, guarantee_deposit=2000.0)
        strategy = ShortStrategy(risk_manager, portfolio_manager)
        
        # Без позиций
        mock_signal = Mock(spec=Signal)
        mock_signal.histogram = 0.2
        mock_signal.atr = None
        mock_signal.candle = Mock()
        mock_signal.candle.close = Quotation(units=2500, nano=0)
        items = await strategy._items_to_sell_short(mock_signal)
        
        # 20% от 100000 = 20000, на 2000 за контракт = 10 контрактов
        # Но лимит items_per_trade = 10, поэтому должно быть 10
        assert items == 10
        
        # С существующей позицией
        strategy._position = 3
        items = await strategy._items_to_sell_short(mock_signal)
        
        # Заморожено 3 * 2000 = 6000, остается 20000 - 6000 = 14000
        # На 2000 за контракт = 7 контрактов
        assert items == 7
    
    @pytest.mark.asyncio
    async def test_items_to_sell_short_zero_guarantee(self):
        """Тест расчета количества при нулевом гарантийном обеспечении"""
        risk_manager = MockRiskManager()
        portfolio_manager = MockPortfolioManager(guarantee_deposit=0.0)
        strategy = ShortStrategy(risk_manager, portfolio_manager)
        
        mock_signal = Mock(spec=Signal)
        mock_signal.histogram = 0.2
        mock_signal.atr = None
        mock_signal.candle = Mock()
        mock_signal.candle.close = Quotation(units=2500, nano=0)
        items = await strategy._items_to_sell_short(mock_signal)
        
        assert items == 0
