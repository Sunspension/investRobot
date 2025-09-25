from datetime import datetime, timedelta

from visualization.chart_builder import ChartBuilder


def _make_candle(t: datetime, o: float, h: float, l: float, c: float, v: int = 1):
    return {
        'time': t,
        'open': o,
        'high': h,
        'low': l,
        'close': c,
        'volume': v,
    }


def test_orders_are_displayed_at_correct_times():
    base = datetime(2025, 9, 15, 12, 0, 0)
    candles = [
        _make_candle(base + timedelta(minutes=i), 100 + i, 101 + i, 99 + i, 100.5 + i)
        for i in range(5)
    ]

    orders = [
            {
                'direction': 'buy',
                'time': base + timedelta(minutes=1),
                'price': 101.0,
                'quantity': 2,
                'strategy': 'TestStrat'
            },
            {
                'direction': 'sell',
                'time': base + timedelta(minutes=3),
                'price': 103.0,
                'quantity': 1,
                'strategy': 'TestStrat'
            },
        ]

    fig = ChartBuilder().create_trading_chart(
        candles_data=candles,
        orders_data=orders,
        current_price=0.0,
    )

    # Expect candlestick trace + 2 order marker traces (buy/sell)
    traces = fig.data
    names = [getattr(tr, 'name', '') for tr in traces]
    assert any('Свечи' in n for n in names)
    assert any('Ордера покупки' in n for n in names)
    assert any('Ордера продажи' in n for n in names)

    # Find order traces and validate coordinates
    buy_trace = next(tr for tr in traces if getattr(tr, 'name', '') == 'Ордера покупки')
    sell_trace = next(tr for tr in traces if getattr(tr, 'name', '') == 'Ордера продажи')

    # Times should match; prices have a small visual offset on markers
    assert list(buy_trace.x) == [orders[0]['time']]
    def _offset(p: float) -> float:
        p = float(p)
        return max(abs(p) * 0.0002, 0.05)
    # Buy markers are displayed slightly below their price
    assert list(buy_trace.y) == [orders[0]['price'] - _offset(orders[0]['price'])]
    assert getattr(buy_trace.marker, 'symbol', None) == 'triangle-up'

    assert list(sell_trace.x) == [orders[1]['time']]
    # Sell markers are displayed slightly above their price
    assert list(sell_trace.y) == [orders[1]['price'] + _offset(orders[1]['price'])]
    assert getattr(sell_trace.marker, 'symbol', None) == 'triangle-down'

    # X-axis is a date axis; ensure layout type is set to 'date' and uses time ticks
    assert fig.layout.xaxis.type == 'date'

