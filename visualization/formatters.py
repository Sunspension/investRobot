from __future__ import annotations
from datetime import datetime

def to_moscow_time(dt: datetime | None) -> datetime:
    """Возвращает naive-datetime в часовом поясе МСК для стабильного отображения в Plotly.

    Если dt без tzinfo, считаем его UTC.
    """
    try:
        import pytz
        msk = pytz.timezone('Europe/Moscow')
        if dt is None:
            return datetime.now(msk).replace(tzinfo=None)
        if dt.tzinfo is None:
            dt = pytz.utc.localize(dt)
        return dt.astimezone(msk).replace(tzinfo=None)
    except Exception:
        return dt if dt is not None else datetime.now()
