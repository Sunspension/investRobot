import types
import asyncio

from visualization.services.portfolio_loader import PortfolioLoader
from visualization.data_manager import VisualizationDataStore


class DummyPortfolio:
    def __init__(self):
        self.total_amount = 100.0
        self.positions = []
        self.pnl = 0.0
        self.blocked_amount = 0.0
        self.available_amount = 100.0


class DummyPM:
    def __init__(self, api):
        self.api = api

    async def get_portfolio(self):
        return DummyPortfolio()


class DummyAPI:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_portfolio_loader(monkeypatch):
    # Подменим зависимости внутри модуля на заглушки
    import visualization.services.portfolio_loader as mod

    class DummyTinkoff:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def pm_factory(api):
        return DummyPM(api)

    monkeypatch.setattr(mod, 'TinkoffAPIClient', DummyTinkoff)
    monkeypatch.setattr(mod, 'PortfolioManager', pm_factory)

    dm = VisualizationDataStore()
    loader = PortfolioLoader()
    asyncio.run(loader.load_into(dm, token='x', account_id='y', sandbox_token=None))

    snap = dm.get_data_snapshot()
    assert snap['portfolio_data']['total_amount'] == 100.0


