"""
Модуль для мониторинга состояния стрима
"""
import asyncio
from datetime import datetime, timezone
from typing import Optional, Callable
from robotlib.utils.logger import get_logger
from robotlib.utils.market_hours_enhanced import get_market_status_enhanced

class StreamWatchdog:
    """Класс для мониторинга состояния стрима и автоматического восстановления"""
    
    def __init__(
        self, 
        stale_seconds: int = 120,
        require_open_market: bool = True,
        check_interval: int = 30
    ):
        """
        Инициализация watchdog
        
        Args:
            stale_seconds: Время в секундах, после которого стрим считается "мертвым"
            require_open_market: Требовать ли открытый рынок для перезапуска
            check_interval: Интервал проверки в секундах
        """
        self._stale_seconds = stale_seconds
        self._require_open_market = require_open_market
        self._check_interval = check_interval
        self._logger = get_logger(__name__)
        self._is_running = False
        self._last_candle_time: Optional[datetime] = None
        self._restart_callback: Optional[Callable[[], None]] = None
    
    def set_last_candle_time(self, last_candle_time: Optional[datetime]) -> None:
        """
        Устанавливает время последней полученной свечи
        
        Args:
            last_candle_time: Время последней свечи
        """
        # Нормализуем время к UTC-aware для безопасной арифметики дат
        if last_candle_time is None:
            self._last_candle_time = None
            return
        if last_candle_time.tzinfo is None:
            self._last_candle_time = last_candle_time.replace(tzinfo=timezone.utc)
        else:
            self._last_candle_time = last_candle_time.astimezone(timezone.utc)
    
    def set_restart_callback(self, callback: Callable[[], None]) -> None:
        """
        Устанавливает callback для перезапуска стрима
        
        Args:
            callback: Функция для перезапуска стрима
        """
        self._restart_callback = callback
    
    async def start_monitoring(self) -> None:
        """Запускает мониторинг стрима"""
        if self._is_running:
            self._logger.warning("Watchdog уже запущен")
            return
        
        self._is_running = True
        self._logger.info(f"Watchdog запущен: stale_seconds={self._stale_seconds}, check_interval={self._check_interval}")
        
        try:
            while self._is_running:
                await asyncio.sleep(self._check_interval)
                if not self._is_running:
                    break
                
                if self._last_candle_time is None:
                    continue
                
                # Используем timezone-aware UTC время
                now_utc = datetime.now(timezone.utc)
                last_utc = (
                    self._last_candle_time if self._last_candle_time.tzinfo is not None
                    else self._last_candle_time.replace(tzinfo=timezone.utc)
                )
                time_since_last_candle = (now_utc - last_utc).total_seconds()
                
                if time_since_last_candle > self._stale_seconds:
                    await self._handle_stale_stream()
                    
        except Exception as e:
            self._logger.error(f"Ошибка в watchdog: {e}")
        finally:
            self._is_running = False
            self._logger.info("Watchdog остановлен")
    
    async def stop_monitoring(self) -> None:
        """Останавливает мониторинг стрима"""
        self._is_running = False
        self._logger.info("Остановка watchdog...")
    
    async def _handle_stale_stream(self) -> None:
        """Обрабатывает ситуацию, когда стрим не получает данные"""
        try:
            # Проверяем, нужно ли требовать открытый рынок
            if self._require_open_market:
                try:
                    status = await get_market_status_enhanced()
                    if not bool(status.get('is_trading', False)):
                        self._logger.info(
                            f"Watchdog: тишина > {self._stale_seconds}с, рынок закрыт — перезапуск пропущен"
                        )
                        return
                except Exception:
                    # В случае ошибки проверки — позволяем перезапуск для надежности
                    pass
            
            self._logger.warning(f"Watchdog: тишина > {self._stale_seconds}с — перезапуск стрима")
            
            # Вызываем callback для перезапуска с защитой от дублирования
            if self._restart_callback:
                try:
                    # Добавляем небольшую задержку для предотвращения частых перезапусков
                    await asyncio.sleep(1.0)
                    self._restart_callback()
                except Exception as e:
                    self._logger.error(f"Ошибка при перезапуске стрима: {e}")
            else:
                self._logger.warning("Callback для перезапуска не установлен")
                
        except Exception as e:
            self._logger.error(f"Ошибка обработки stale stream: {e}")
    
    @property
    def is_running(self) -> bool:
        """Проверяет, запущен ли watchdog"""
        return self._is_running
    
    @property
    def stale_seconds(self) -> int:
        """Возвращает время stale в секундах"""
        return self._stale_seconds
    
    @property
    def last_candle_time(self) -> Optional[datetime]:
        """Возвращает время последней свечи"""
        return self._last_candle_time
