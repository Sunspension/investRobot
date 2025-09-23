"""
Мок для визуализатора событий
"""
from typing import Optional, Any
from robotlib.utils.logger import get_logger

class MockEventVisualizer:
    """Мок визуализатора событий для тестирования (без сигналов)"""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8050, start_server: bool = True):
        self.host = host
        self.port = port
        self.start_server = start_server
        self._running = False
        self._logger = get_logger(__name__)
    
    async def start(self) -> None:
        """Запускает мок-визуализатор"""
        if self._running:
            self._logger.warning("Мок-визуализатор уже запущен")
            return
        
        self._running = True
        if self.start_server:
            self._logger.info(f"🎭 Мок-визуализатор запущен на http://{self.host}:{self.port}")
        else:
            self._logger.info("🎭 Мок-визуализатор готов (сервер отключен)")
    
    async def stop(self) -> None:
        """Останавливает мок-визуализатор"""
        if not self._running:
            self._logger.warning("Мок-визуализатор не запущен")
            return
        
        self._running = False
        self._logger.info("🎭 Мок-визуализатор остановлен")
    
    @property
    def is_running(self) -> bool:
        """Флаг работы мок-визуализатора"""
        return self._running
    
    def add_candle(self, timestamp: str, price: float) -> None:
        """Добавляет мок-свечу"""
        self._logger.info(f"🎭 Добавлена мок-свеча: {timestamp} @ {price}")
    
    def get_stats(self) -> dict:
        """Возвращает мок-статистику"""
        return {
            'candles_count': 100,
            'is_running': self._running
        }

