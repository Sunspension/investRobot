from __future__ import annotations

from datetime import datetime, timedelta, time as _time
from typing import Dict, Any

from robotlib.utils.logger import get_logger
from robotlib.utils.market_hours_enhanced import get_market_status_enhanced


class MarketStatusService:
    """Сервис расчёта статуса рынка и таймеров в МСК.

    Выделен из DashEventVisualizer для переиспользования и тестирования.
    """

    def __init__(self) -> None:
        self._logger = get_logger(__name__)

    async def get_enhanced_status(self) -> Dict[str, Any]:
        """Возвращает словарь статуса рынка (as-is из get_market_status_enhanced())."""
        try:
            return await get_market_status_enhanced()
        except Exception as e:
            self._logger.error(f"Ошибка получения статуса рынка: {e}")
            return {"is_trading": False, "status": "Ошибка"}

    def countdown_to_close_text(self, session_type: str) -> str:
        """Возвращает строку обратного отсчёта до конца текущей сессии (МСК)."""
        try:
            import pytz as _pytz
            msk = _pytz.timezone('Europe/Moscow')
            now_msk = datetime.now(msk)

            if session_type == 'main':
                session_end = now_msk.replace(hour=18, minute=45, second=0, microsecond=0)
            elif session_type == 'evening':
                session_end = now_msk.replace(hour=23, minute=50, second=0, microsecond=0)
            elif session_type == 'weekend':
                session_end = now_msk.replace(hour=18, minute=0, second=0, microsecond=0)
            else:
                session_end = now_msk

            if session_end <= now_msk:
                remaining = "00:00:00"
            else:
                delta = session_end - now_msk
                hours = delta.days * 24 + delta.seconds // 3600
                minutes = (delta.seconds % 3600) // 60
                seconds = delta.seconds % 60
                remaining = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

            return f"До окончания: {remaining}"
        except Exception as e:
            self._logger.error(f"Ошибка расчёта таймера до закрытия: {e}")
            return "До окончания: —"

    def countdown_to_open_text(self) -> str:
        """Возвращает строку обратного отсчёта до следующего открытия (МСК)."""
        try:
            import pytz as _pytz
            msk = _pytz.timezone('Europe/Moscow')
            now_msk = datetime.now(msk)
            next_open = now_msk.replace(hour=10, minute=0, second=0, microsecond=0)
            if now_msk >= next_open:
                next_open = next_open + timedelta(days=1)
            delta = next_open - now_msk
            hours = delta.days * 24 + delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60
            seconds = delta.seconds % 60
            return f"До открытия: {hours:02d}:{minutes:02d}:{seconds:02d}"
        except Exception as e:
            self._logger.error(f"Ошибка расчёта таймера до открытия: {e}")
            return "До открытия: —"


