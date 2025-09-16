import re

from visualization.services.market_status_service import MarketStatusService


def test_countdown_to_close_text_returns_string():
    svc = MarketStatusService()
    txt = svc.countdown_to_close_text('main')
    assert txt.startswith('До окончания:')
    assert re.match(r'^До окончания: \d{2}:\d{2}:\d{2}$', txt)


def test_countdown_to_open_text_returns_string():
    svc = MarketStatusService()
    txt = svc.countdown_to_open_text()
    assert txt.startswith('До открытия:')
    assert re.match(r'^До открытия: \d{2}:\d{2}:\d{2}$', txt)


