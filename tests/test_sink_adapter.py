import asyncio
from datetime import datetime
from unittest.mock import Mock

from visualization.adapters.sink_impl import DataManagerSink, WsEventBroadcaster, TradingToUIBridge
from visualization.data_manager import DataManager
from visualization.formatters import to_moscow_time


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
    bridge = TradingToUIBridge(DataManagerSink(data_manager), WsEventBroadcaster(broadcast_mock))
    
    candle = MockCandle(
        time=datetime(2024, 1, 1, 12, 0, 0),
        open_val=100,
        high_val=105,
        low_val=95,
        close_val=102,
        volume=1000
    )
    
    asyncio.run(bridge.on_candle(candle, 102.0, "TESTFIGI"))
    
    # Проверяем, что данные добавились в DataManager через публичный API
    snapshot = data_manager.get_data_snapshot()
    assert len(snapshot['candles_data']) == 1
    candle_data = snapshot['candles_data'][0]
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
    bridge = TradingToUIBridge(DataManagerSink(data_manager), WsEventBroadcaster(broadcast_mock))
    
    signal = MockSignal(histogram=0.5, macd=1.2, signal=0.7)
    
    asyncio.run(bridge.on_signal(signal, "TESTFIGI", 102.0))
    
    # Проверяем, что сигнал добавился в DataManager через публичный API
    snapshot = data_manager.get_data_snapshot()
    assert len(snapshot['signals_data']) == 1
    signal_data = snapshot['signals_data'][0]
    assert signal_data['type'] == 'buy'  # histogram > 0
    assert signal_data['strength'] == 0.5
    assert signal_data['price'] == 102.0
    # on_signal не рассылает WS-сообщения
    broadcast_mock.assert_not_called()


def test_sink_adapter_on_market_status():
    data_manager = DataManager()
    broadcast_mock = Mock()
    bridge = TradingToUIBridge(DataManagerSink(data_manager), WsEventBroadcaster(broadcast_mock))
    
    status = {'is_trading': True, 'session': 'main'}
    
    asyncio.run(bridge.on_market_status(status))
    
    # Проверяем, что статус обновился в DataManager через публичный API
    snapshot = data_manager.get_data_snapshot()
    assert snapshot['market_status']['is_trading'] is True
    assert snapshot['market_status']['session'] == 'main'
    
    # Проверяем, что broadcast был вызван
    broadcast_mock.assert_called_once()
    call_args = broadcast_mock.call_args[0][0]
    assert call_args['type'] == 'market_status'
    assert call_args['is_trading'] is True


def test_sink_adapter_error_handling():
    data_manager = DataManager()
    broadcast_mock = Mock()
    bridge = TradingToUIBridge(DataManagerSink(data_manager), WsEventBroadcaster(broadcast_mock))
    
    # Тестируем обработку ошибок в on_candle
    invalid_candle = Mock()
    invalid_candle.time = None  # Это вызовет ошибку при обработке
    
    asyncio.run(bridge.on_candle(invalid_candle, 100.0, "TESTFIGI"))
    
    # DataManager должен остаться пустым из-за ошибки через публичный API
    snapshot = data_manager.get_data_snapshot()
    assert len(snapshot['candles_data']) == 0
    # broadcast не должен вызываться при ошибке
    broadcast_mock.assert_not_called()


def test_sink_adapter_on_signal_sell():
    data_manager = DataManager()
    broadcast_mock = Mock()
    bridge = TradingToUIBridge(DataManagerSink(data_manager), WsEventBroadcaster(broadcast_mock))
    
    signal = MockSignal(histogram=-0.3, macd=-1.0, signal=-0.5)
    
    asyncio.run(bridge.on_signal(signal, "TESTFIGI", 99.0))
    
    snapshot = data_manager.get_data_snapshot()
    assert len(snapshot['signals_data']) == 1
    signal_data = snapshot['signals_data'][0]
    assert signal_data['type'] == 'sell'
    assert signal_data['strength'] == 0.3
    assert signal_data['price'] == 99.0
    # on_signal не должен делать broadcast
    broadcast_mock.assert_not_called()


def test_sink_adapter_on_candle_broadcast_time_format_utc():
    import pytz
    data_manager = DataManager()
    broadcast_mock = Mock()
    bridge = TradingToUIBridge(DataManagerSink(data_manager), WsEventBroadcaster(broadcast_mock))
    
    utc_dt = pytz.utc.localize(datetime(2024, 1, 1, 12, 0, 0))
    candle = MockCandle(
        time=utc_dt,
        open_val=100,
        high_val=105,
        low_val=95,
        close_val=102,
        volume=1000
    )
    
    asyncio.run(bridge.on_candle(candle, 102.0, "TESTFIGI"))
    
    broadcast_mock.assert_called_once()
    call = broadcast_mock.call_args[0][0]
    assert call['type'] == 'candle'
    # Ожидаемая строка времени после конвертации в МСК (naive)
    expected_dt = to_moscow_time(utc_dt)
    assert call['time'] == str(expected_dt)
