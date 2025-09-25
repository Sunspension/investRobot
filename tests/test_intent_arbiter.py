import pytest

from robotlib.strategies.intent_arbiter import SimpleIntentArbiter
from robotlib.trading.order_types import OrderIntent, OrderDirection, OrderType


def test_simple_intent_arbiter_nets_buy_and_sell():
    arb = SimpleIntentArbiter()
    intents = [
        OrderIntent(figi="F1", direction=OrderDirection.BUY, order_type=OrderType.MARKET, quantity=3),
        OrderIntent(figi="F1", direction=OrderDirection.SELL, order_type=OrderType.MARKET, quantity=1),
        OrderIntent(figi="F1", direction=OrderDirection.BUY, order_type=OrderType.MARKET, quantity=2),
    ]
    arb.add_intents(intents)
    out = arb.flush()
    assert len(out) == 1
    res = out[0]
    assert res.figi == "F1"
    assert res.direction == OrderDirection.BUY
    assert res.quantity == 4  # 3 - 1 + 2


def test_simple_intent_arbiter_zero_net_drops():
    arb = SimpleIntentArbiter()
    intents = [
        OrderIntent(figi="F1", direction=OrderDirection.BUY, order_type=OrderType.MARKET, quantity=5),
        OrderIntent(figi="F1", direction=OrderDirection.SELL, order_type=OrderType.MARKET, quantity=5),
    ]
    arb.add_intents(intents)
    out = arb.flush()
    assert out == []


def test_simple_intent_arbiter_multi_figi():
    arb = SimpleIntentArbiter()
    intents = [
        OrderIntent(figi="A", direction=OrderDirection.BUY, order_type=OrderType.MARKET, quantity=1),
        OrderIntent(figi="B", direction=OrderDirection.SELL, order_type=OrderType.MARKET, quantity=2),
        OrderIntent(figi="A", direction=OrderDirection.BUY, order_type=OrderType.MARKET, quantity=2),
    ]
    arb.add_intents(intents)
    out = sorted(arb.flush(), key=lambda x: x.figi)
    assert len(out) == 2
    a, b = out
    assert a.figi == "A" and a.direction == OrderDirection.BUY and a.quantity == 3
    assert b.figi == "B" and b.direction == OrderDirection.SELL and b.quantity == 2


