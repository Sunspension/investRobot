"""
Конфигурация стрима рыночных данных (watchdog и связанные параметры)
"""


class StreamConfig:
    """Настройки стрима рыночных данных."""
    def __init__(
        self,
        *,
        watchdog_enabled: bool = True,
        watchdog_stale_seconds: int = 120,
        watchdog_require_open_market: bool = True,
    ):
        self.watchdog_enabled = watchdog_enabled
        self.watchdog_stale_seconds = watchdog_stale_seconds
        self.watchdog_require_open_market = watchdog_require_open_market


