"""
Тесты для ShortStrategy
"""
import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from robotlib.strategies.short import ShortStrategy
from tests.mocks.position_sizer_dummy import DummySizer
from robotlib.signal_types import Signal
from robotlib.trading.order_types import OrderIntent, OrderExecution, OrderDirection, OrderType, OrderStatus
from robotlib.trading.interfaces import PositionManageable
from robotlib.trading.position_sync_interface import PositionContext
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
        pass
    
    async def get_loss_positions(self, figi: str, current_price: float, loss_threshold: float = None):
        """Получение убыточных позиций"""
        if loss_threshold is None:
            loss_threshold = self._risk_manager.risk_limits.stop_loss_threshold
        
        # Для тестов возвращаем убыточные позиции, если убыток превышает порог в пунктах
        # Создаем тестовые позиции с ценой 100, если текущая цена выросла достаточно
        if current_price >= 100.0 + loss_threshold:  # Если цена выросла на loss_threshold пунктов
            from robotlib.trading.position_manager import FIFOEntry, LossPosition
            fifo_entry = FIFOEntry(quantity=2, price=100.0, timestamp=datetime.now(), order_id="test", direction="short")
            loss_percent = (current_price - 100.0) / 100.0
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


class TestShortStrategy:
    """Тесты для ShortStrategy"""
    
    def test_init(self):
        """Тест инициализации стратегии"""
        mock_position_sizing_service = Mock()
        mock_position_sizing_service.calculate_position_size = AsyncMock(return_value=1)
        strategy = ShortStrategy(figi="FUTIMOEXF000", position_sizing_service=mock_position_sizing_service)
        
        assert strategy._wait_short_sell_cross is False
        assert strategy._wait_short_buy_cross is False
        assert strategy.strategy_name == "ShortStrategy"
        assert strategy._figi == "FUTIMOEXF000"
    
    def test_init_with_custom_figi(self):
        """Тест инициализации стратегии с кастомным figi"""
        mock_position_sizing_service = Mock()
        strategy = ShortStrategy(figi="CUSTOM_FIGI", position_sizing_service=mock_position_sizing_service)
        
        assert strategy._figi == "CUSTOM_FIGI"
    
    @pytest.mark.asyncio
    async def test_initialize(self):
        """Тест инициализации с параметрами"""
        mock_position_sizing_service = Mock()
        mock_position_sizing_service.calculate_position_size = AsyncMock(return_value=1)
        strategy = ShortStrategy(figi="FUTIMOEXF000", position_sizing_service=mock_position_sizing_service)
        
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
        mock_position_sizing_service = Mock()
        mock_position_sizing_service.calculate_position_size = AsyncMock(return_value=1)
        strategy = ShortStrategy(figi="FUTIMOEXF000", position_sizing_service=mock_position_sizing_service)
        
        strategy.initialize(point_value=10.0, contracts_per_lot=10)
        
        assert strategy._figi == "FUTIMOEXF000"
        assert strategy._point_value == 10.0
        assert strategy._contracts_per_lot == 10
    
    @pytest.mark.asyncio
    async def test_execute_no_signal(self):
        """Тест выполнения без сигналов"""
        mock_position_sizing_service = Mock()
        mock_position_sizing_service.calculate_position_size = AsyncMock(return_value=1)
        strategy = ShortStrategy(figi="FUTIMOEXF000", position_sizing_service=mock_position_sizing_service)
        
        signal = create_signal(
            macd=0.1,
            signal=0.1,
            histogram=0.0,
            peak_detected=False,
            trough_detected=False
        )
        
        # Создаем контекст позиции
        position_context = create_position_context()
        
        orders = await strategy.execute(signal, position_context)
        
        assert orders == []
        assert strategy._wait_short_sell_cross is False
        assert strategy._wait_short_buy_cross is False
    
    @pytest.mark.asyncio
    async def test_execute_peak_detected(self):
        """Тест обнаружения пика (сигнал на шорт)"""
        mock_position_sizing_service = Mock()
        mock_position_sizing_service.calculate_position_size = AsyncMock(return_value=1)
        strategy = ShortStrategy(figi="FUTIMOEXF000", position_sizing_service=mock_position_sizing_service)
        
        signal = create_signal(peak_detected=True)
        
        # Создаем контекст позиции
        position_context = create_position_context()
        
        orders = await strategy.execute(signal, position_context)
        
        assert strategy._wait_short_sell_cross is True
        assert strategy._wait_short_buy_cross is False
    
    @pytest.mark.asyncio
    async def test_execute_trough_detected(self):
        """Тест обнаружения впадины (сигнал на закрытие шорта)"""
        mock_position_sizing_service = Mock()
        mock_position_sizing_service.calculate_position_size = AsyncMock(return_value=1)
        strategy = ShortStrategy(figi="FUTIMOEXF000", position_sizing_service=mock_position_sizing_service)
        
        signal = create_signal(trough_detected=True)
        
        # Создаем контекст позиции
        position_context = create_position_context()
        
        orders = await strategy.execute(signal, position_context)
        
        assert strategy._wait_short_sell_cross is False
        assert strategy._wait_short_buy_cross is True
    
    @pytest.mark.asyncio
    async def test_execute_short_sell_signal(self):
        """Тест сигнала на открытие шорта"""
        mock_position_sizing_service = Mock()
        mock_position_sizing_service.calculate_position_size = AsyncMock(return_value=1)
        strategy = ShortStrategy(figi="FUTIMOEXF000", position_sizing_service=mock_position_sizing_service)
        
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
        
        # Создаем контекст позиции
        position_context = create_position_context()
        
        orders = await strategy.execute(signal, position_context)
        
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
        mock_position_sizing_service = Mock()
        mock_position_sizing_service.calculate_position_size = AsyncMock(return_value=1)
        strategy = ShortStrategy(figi="FUTIMOEXF000", position_sizing_service=mock_position_sizing_service)
        
        # Устанавливаем ожидание закрытия шорта
        strategy._wait_short_buy_cross = True
        
        signal = create_signal(
            macd=0.5,
            signal=0.3,
            macd_prev=0.2,
            signal_prev=0.4,
            histogram=0.2,
            trough_detected=False
        )
        
        # Создаем контекст позиции с позицией
        position_context = create_position_context(quantity=5, has_position=True, direction='short')
        
        orders = await strategy.execute(signal, position_context)
        
        assert len(orders) == 1
        assert isinstance(orders[0], OrderIntent)
        assert orders[0].direction == OrderDirection.BUY
        assert orders[0].order_type == OrderType.MARKET
        assert orders[0].figi == "FUTIMOEXF000"
        assert orders[0].quantity == 1  # PositionSizingService возвращает 1
        assert strategy._wait_short_buy_cross is False
    
    @pytest.mark.asyncio
    async def test_execute_trending_down(self):
        """Тест дозакупки при нисходящем тренде"""
        mock_position_sizing_service = Mock()
        mock_position_sizing_service.calculate_position_size = AsyncMock(return_value=1)
        strategy = ShortStrategy(figi="FUTIMOEXF000", position_sizing_service=mock_position_sizing_service)
        
        signal = create_signal(
            macd=0.2,
            signal=0.4,
            macd_prev=0.5,
            signal_prev=0.3,
            histogram=0.2
        )
        
        # Создаем контекст позиции с позицией
        position_context = create_position_context(quantity=2, has_position=True, direction='short')
        
        orders = await strategy.execute(signal, position_context)
        
        assert len(orders) == 1
        assert orders[0].direction == OrderDirection.SELL
        assert orders[0].quantity > 0
    
    
    
    
    
    
    # Тесты _check_stop_loss удалены - логика перенесена в StrategyManager
    


def create_position_context(figi: str = "FUTIMOEXF000", quantity: int = 0, avg_price: float = 0.0, 
                           has_position: bool = False, direction: str = '') -> PositionContext:
    """Создание мока PositionContext для тестов"""
    return PositionContext(
        figi=figi,
        quantity=quantity,
        avg_price=avg_price,
        has_position=has_position,
        direction=direction,
        last_updated=datetime.now()
    )
