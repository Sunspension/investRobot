import asyncio
from datetime import datetime
from unittest.mock import Mock

from visualization.adapters.sink_impl import VisualizationSinkAdapter
from visualization.data_manager import DataManager


class MockCandle:
    def __init__(self, time, open_val, high_val, low_val, close_val, volume):
        self.time = time
        self.open = Mock(units=open_val, nano=0)
        self.high = Mock(units=high_val, nano=0)
        self.low = Mock(units=low_val, nano=0)
        self.close = Mock(units=close_val, nano=0)
        self.volume = volume


class MockSignal:
    def __init__(self, histogram, macd, signal):
        self.histogram = histogram
        self.macd = macd
        self.signal = signal


def test_sink_adapter_on_candle():
    data_manager = DataManager()
    broadcast_mock = Mock()
    adapter = VisualizationSinkAdapter(data_manager, broadcast_mock)
    
    candle = MockCandle(
        time=datetime(2024, 1, 1, 12, 0, 0),
        open_val=100,
        high_val=105,
        low_val=95,
        close_val=102,
        volume=1000
    )
    
    asyncio.run(adapter.on_candle(candle, 102.0, "TESTFIGI"))
    
    # Проверяем, что данные добавились в DataManager
    assert len(data_manager.candles_data) == 1
    candle_data = data_manager.candles_data[0]
    assert candle_data['open'] == 100.0
    assert candle_data['close'] == 102.0
    assert candle_data['volume'] == 1000
    
    # Проверяем, что broadcast был вызван
    broadcast_mock.assert_called_once()
    call_args = broadcast_mock.call_args[0][0]
    assert call_args['type'] == 'candle'
    assert call_args['price'] == 102.0


def test_sink_adapter_on_signal():
    data_manager = DataManager()
    broadcast_mock = Mock()
    adapter = VisualizationSinkAdapter(data_manager, broadcast_mock)
    
    signal = MockSignal(histogram=0.5, macd=1.2, signal=0.7)
    
    asyncio.run(adapter.on_signal(signal, "TESTFIGI", 102.0))
    
    # Проверяем, что сигнал добавился в DataManager
    assert len(data_manager.signals_data) == 1
    signal_data = data_manager.signals_data[0]
    assert signal_data['type'] == 'buy'  # histogram > 0
    assert signal_data['strength'] == 0.5
    assert signal_data['price'] == 102.0


def test_sink_adapter_on_market_status():
    data_manager = DataManager()
    broadcast_mock = Mock()
    adapter = VisualizationSinkAdapter(data_manager, broadcast_mock)
    
    status = {'is_trading': True, 'session': 'main'}
    
    asyncio.run(adapter.on_market_status(status))
    
    # Проверяем, что статус обновился в DataManager
    assert data_manager.market_status['is_trading'] is True
    assert data_manager.market_status['session'] == 'main'
    
    # Проверяем, что broadcast был вызван
    broadcast_mock.assert_called_once()
    call_args = broadcast_mock.call_args[0][0]
    assert call_args['type'] == 'market_status'
    assert call_args['is_trading'] is True


def test_sink_adapter_error_handling():
    data_manager = DataManager()
    broadcast_mock = Mock()
    adapter = VisualizationSinkAdapter(data_manager, broadcast_mock)
    
    # Тестируем обработку ошибок в on_candle
    invalid_candle = Mock()
    invalid_candle.time = None  # Это вызовет ошибку при обработке
    
    asyncio.run(adapter.on_candle(invalid_candle, 100.0, "TESTFIGI"))
    
    # DataManager должен остаться пустым из-за ошибки
    assert len(data_manager.candles_data) == 0
