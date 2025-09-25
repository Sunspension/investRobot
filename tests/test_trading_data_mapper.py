from datetime import datetime
from unittest.mock import Mock

from visualization.adapters.sink_impl import TradingDataMapper
from visualization.data_manager import VisualizationDataStore


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


def test_trading_data_mapper_add_candle():
    dm = VisualizationDataStore()
    mapper = TradingDataMapper(dm)

    candle = MockCandle(
        time=datetime(2024, 1, 1, 12, 0, 0),
        open_val=100,
        high_val=105,
        low_val=95,
        close_val=102,
        volume=1000,
    )

    mapper.add_candle(candle)

    snap = dm.get_data_snapshot()
    assert len(snap['candles_data']) == 1
    c = snap['candles_data'][0]
    assert c['open'] == 100.0
    assert c['close'] == 102.0
    assert c['volume'] == 1000


def test_trading_data_mapper_add_signal():
    dm = VisualizationDataStore()
    mapper = TradingDataMapper(dm)
    sig = MockSignal(histogram=0.4, macd=1.1, signal=0.7)

    mapper.add_signal(sig, 101.0)

    snap = dm.get_data_snapshot()
    assert len(snap['signals_data']) == 1
    s = snap['signals_data'][0]
    assert s['type'] == 'buy'
    assert s['strength'] == 0.4
    assert s['price'] == 101.0


def test_trading_data_mapper_add_market_status_and_order():
    dm = VisualizationDataStore()
    mapper = TradingDataMapper(dm)

    # Market status
    status = {'is_trading': True, 'session': 'main'}
    mapper.add_market_status(status)
    snap = dm.get_data_snapshot()
    assert snap['market_status']['is_trading'] is True
    assert snap['market_status']['session'] == 'main'

    # Order
    execution = Mock(order_id='ord1', timestamp=datetime(2024, 1, 1, 12, 0, 0), price=100.5, filled_quantity=3, reason='test')
    intent = Mock(figi='TEST', side='buy', quantity=3, strategy='str1')
    
    # Настраиваем Mock объекты для правильной работы с float()
    execution.price = 100.5
    execution.executed_price = None
    mapper.add_order(execution, intent)
    snap = dm.get_data_snapshot()
    assert len(snap['orders_data']) == 1
    o = snap['orders_data'][0]
    assert o['order_id'] == 'ord1'
    assert o['figi'] == 'TEST'
    assert o['quantity'] == 3

