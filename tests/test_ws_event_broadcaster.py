from datetime import datetime
from unittest.mock import Mock

from visualization.adapters.sink_impl import WsEventBroadcaster


def test_ws_emit_candle():
    mock_broadcast = Mock()
    ws = WsEventBroadcaster(mock_broadcast)
    ts = datetime(2024, 1, 1, 12, 0, 0)

    ws.emit_candle(101.5, ts)

    mock_broadcast.assert_called_once()
    msg = mock_broadcast.call_args[0][0]
    assert msg['type'] == 'candle'
    assert msg['price'] == 101.5
    assert 'time' in msg


def test_ws_emit_signal_and_status_and_order():
    mock_broadcast = Mock()
    ws = WsEventBroadcaster(mock_broadcast)

    ws.emit_signal('buy', 100.0)
    ws.emit_market_status(True)
    ws.emit_order('sell', 99.0)

    assert mock_broadcast.call_count == 3
    calls = [c[0][0] for c in mock_broadcast.call_args_list]
    assert calls[0]['type'] == 'signal' and calls[0]['side'] == 'buy'
    assert calls[1]['type'] == 'market_status' and calls[1]['is_trading'] is True
    assert calls[2]['type'] == 'order' and calls[2]['side'] == 'sell' and calls[2]['price'] == 99.0

