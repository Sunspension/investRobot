import asyncio

from robotlib.signal_manager import SignalManager
from robotlib.strategies.strategy_manager import StrategyManager
from robotlib.strategies.intent_arbiter import SimpleIntentArbiter
from robotlib.strategies.signal_dispatcher import NullSignalDispatcher


class DummyRisk:
    risk_limits = None


class DummyPortfolio:
    async def get_portfolio(self):
        class P: total_amount = 0.0
        return P()


class DummyExecutor:
    def __init__(self):
        self.calls = 0
    async def execute_order(self, oi):
        self.calls += 1
        return None


class DummyDispatcher:
    def __init__(self):
        self.dispatched = 0
    async def dispatch_signal(self, *args, **kwargs):
        self.dispatched += 1


class DummyPositionManager:
    async def get_position(self, figi: str):
        return None
    async def add_to_fifo(self, figi: str, quantity: int, price: float, order_id: str):
        pass


def test_warmup_no_dispatch_no_orders():
    sm = SignalManager()
    dispatcher = DummyDispatcher()
    executor = DummyExecutor()
    
    # Создаем пустой список стратегий
    strategies = []
    
    mgr = StrategyManager(
        signal_manager=sm,
        risk_manager=DummyRisk(),
        portfolio_manager=DummyPortfolio(),
        order_executor=executor,
        strategies=strategies,
        signal_dispatcher=NullSignalDispatcher(),
        intent_arbiter=SimpleIntentArbiter(),
        position_manager=DummyPositionManager(),
    )

    # 50 баров
    bars = [
        {"time": i, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.0 + i * 0.01}
        for i in range(50)
    ]

    asyncio.run(mgr.warmup_with_bars(bars, dispatch_signals=False, place_orders=False))

    assert dispatcher.dispatched == 0
    assert executor.calls == 0


