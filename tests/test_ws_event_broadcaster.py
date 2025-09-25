from datetime import datetime
from unittest.mock import Mock

from visualization.adapters.sink_impl import WsEventBroadcaster


def test_ws_emit_candle():
    mock_broadcast = Mock()
    ws = WsEventBroadcaster(mock_broadcast)
    ts = datetime(2024, 1, 1, 12, 0, 0)

    candle_update = {
        'type': 'candle_added',
        'candle': {
            'time': ts,
            'close': 101.5,
            'open': 100.0,
            'high': 102.0,
            'low': 99.0,
            'volume': 1000
        }
    }
    ws.emit_candle_update(candle_update)

    mock_broadcast.assert_called_once()
    msg = mock_broadcast.call_args[0][0]
    assert msg['type'] == 'candle_added'
    assert msg['candle']['close'] == 101.5
    assert 'time' in msg['candle']


def test_ws_emit_signal_and_status_and_order():
    mock_broadcast = Mock()
    ws = WsEventBroadcaster(mock_broadcast)

    signal_update = {
        'type': 'signal_added',
        'signal': {
            'type': 'buy',
            'price': 100.0,
            'time': datetime.now()
        }
    }
    ws.emit_signal_update(signal_update)
    
    snapshot_data = {
        'market_status': {'is_trading': True},
        'orders_data': [],
        'candles_data': []
    }
    ws.emit_snapshot(snapshot_data)

    assert mock_broadcast.call_count == 2
    calls = [c[0][0] for c in mock_broadcast.call_args_list]
    assert calls[0]['type'] == 'signal_added' and calls[0]['signal']['type'] == 'buy'
    assert calls[1]['type'] == 'snapshot' and calls[1]['data']['market_status']['is_trading'] is True

