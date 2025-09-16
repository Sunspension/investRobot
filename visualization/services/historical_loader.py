from __future__ import annotations

import os
from typing import Optional

from robotlib.utils.logger import get_logger


class HistoricalLoader:
    """Сервис начальной подгрузки исторических свечей из SQLite в DataManager."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._logger = get_logger(__name__)
        self._db_path = db_path or os.path.join(os.getcwd(), "data", "candles.db")

    def load_into(self, data_manager, figi: str, limit: int = 200) -> None:
        try:
            if os.path.exists(self._db_path):
                self._logger.info(f"🔄 Загружаем исторические данные из {self._db_path}")
                data_manager.load_historical_candles(self._db_path, figi, limit=limit)
                self._logger.info(
                    f"✅ Загружено {len(data_manager.candles_data)} исторических свечей"
                )
            else:
                self._logger.warning(f"⚠️ База данных не найдена: {self._db_path}")
        except Exception as e:
            self._logger.error(f"❌ Ошибка загрузки исторических данных: {e}")


