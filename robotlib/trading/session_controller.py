"""
Класс для управления жизненным циклом торговой сессии
"""
import asyncio
import pytz
from datetime import datetime, timedelta
from typing import Optional
from datetime import datetime, timedelta
from robotlib.trading.interfaces import TradingDependencies
from robotlib.trading.session_interfaces import SessionControllable, SessionStatsable
from robotlib.trading.trading_config import TradingConfig
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from visualization.event_visualizer_interface import EventVisualizerable
from robotlib.utils.market_hours import get_market_status_with_api
from robotlib.utils.market_hours_enhanced import get_market_status_enhanced
from robotlib.utils.logger import get_logger


class SessionController(SessionControllable):
    """Класс для управления жизненным циклом торговой сессии"""
    
    def __init__(
        self, 
        config: TradingConfig, 
        dependencies: TradingDependencies, 
        force_start: bool = False,
        visualizer: Optional['EventVisualizerable'] = None
    ):
        self._config = config
        self._dependencies = dependencies
        self._force_start = force_start
        self._visualizer = visualizer
        self._logger = get_logger(__name__)
        # Компоненты из зависимостей
        self._stats = dependencies.session_stats
        self._initializer = dependencies.session_initializer
        # Состояние сессии
        self._is_running = False
        self._is_initialized = False
    
    @property
    def is_running(self) -> bool:
        """Флаг работы сессии"""
        return self._is_running
    
    @property
    def is_initialized(self) -> bool:
        """Флаг инициализации сессии"""
        return self._is_initialized
    
    @property
    def stats(self) -> SessionStatsable:
        """Статистика сессии"""
        return self._stats
    
    @property
    def config(self) -> TradingConfig:
        """Конфигурация торговли"""
        return self._config
    
    @property
    def dependencies(self) -> TradingDependencies:
        """Зависимости торговой системы"""
        return self._dependencies
    
    @property
    def force_start(self) -> bool:
        """Принудительный запуск"""
        return self._force_start
    
    @property
    def visualizer(self) -> Optional['EventVisualizerable']:
        """Визуализатор"""
        return self._visualizer
    
    async def _load_initial_candles(self) -> None:
        try:
            dm = self._dependencies.data_manager
            dm.load_recent_candles(
                db_path="data/market.db",
                figi=self._config.figi,
                limit=300,
            )
            self._logger.info(f"Начальные свечи загружены: {len(dm.candles_data)} шт.")
        except Exception as e:
            self._logger.warning(f"Не удалось загрузить начальные свечи для визуализатора: {e}")

    async def _publish_initial_portfolio(self) -> None:
        try:
            portfolio_data = await self._dependencies.portfolio_manager.get_portfolio_data()
            dm = self._dependencies.data_manager
            dm.update_portfolio(portfolio_data)
            self._logger.info("Портфель опубликован в UI (старт)")
                
        except Exception as e:
            self._logger.warning(f"Не удалось опубликовать портфель на старте: {e}")


    async def _warmup_strategies(self) -> None:
        try:
            dm = self._dependencies.data_manager
            snapshot = dm.get_data_snapshot()
            candles = snapshot.get('candles_data', [])
            if candles:
                bars = [
                    {
                        'time': c['time'],
                        'open': float(c['open']),
                        'high': float(c['high']),
                        'low': float(c['low']),
                        'close': float(c['close']),
                    }
                    for c in candles[-200:]
                ]
                await self._dependencies.strategy_manager.warmup_with_bars(
                    bars,
                    dispatch_signals=False,
                    place_orders=False,
                )
                self._logger.info(f"Прогрето стратегий барами: {len(bars)}")
        except Exception as e:
            self._logger.warning(f"Прогрев стратегий пропущен: {e}")

    async def start(self) -> bool:
        """Запускает торговую сессию"""
        self._logger.info("Запуск торговой сессии...")
        
        try:
            if not await self._check_market_status():
                return False
            await self._initializer.initialize_components()
            self._is_initialized = True
            await self._load_initial_candles()

            if self._visualizer:
                await self._visualizer.start()
                self._logger.info("✅ Dash визуализатор событий запущен")
                await self._publish_initial_portfolio()

            await self._warmup_strategies()
            await self._log_session_info()
            
            self._is_running = True
            self._logger.info("Торговая сессия успешно запущена")
            return True
        
        except Exception as e:
            self._logger.error(f"Ошибка при запуске сессии: {e}")
            return False
    
    async def stop(self) -> None:
        """Останавливает торговую сессию"""
        self._logger.info("Остановка торговой сессии...")
        try:
            # Закрываем все позиции если нужно
            if self._config.auto_close_positions:
                await self._close_all_positions()
            # Останавливаем визуализатор
            if self._visualizer:
                await self._visualizer.stop()
                self._logger.info("Визуализатор остановлен")
            # Останавливаем поток данных (обязательная зависимость)
            await self._dependencies.market_data_stream.stop()
            # Завершаем статистику
            self._stats.finish_session()
            # Выводим финальную статистику
            self._stats.print_stats()
            self._is_running = False
            self._logger.info("Торговая сессия остановлена")
            
        except Exception as e:
            self._logger.error(f"Ошибка при остановке сессии: {e}")
    
    async def _handle_grpc_cancelled(self, error_msg: str) -> None:
        self._logger.warning(f"gRPC стрим отменен: {error_msg}")
        self._logger.info("Перезапуск стрима...")
        self._dependencies.market_data_stream.reset()
        await asyncio.sleep(2)
        await self._dependencies.market_data_stream.start()

    async def _handle_generic_error_with_recovery(self, err: Exception) -> None:
        self._logger.error(f"Ошибка в торговом цикле: {err}")
        self._logger.info("Пауза торговли до восстановления...")
        await self._wait_for_api_recovery()
        self._logger.info("Торговля возобновлена")

    async def _maybe_close_positions_eod(self) -> bool:
        """Возвращает True, если день закрыт и позиции закрыты (нужно выйти из цикла)."""
        if not self._config.end_of_day_close:
            return False
        time_to_close = await self._get_time_to_close()
        if time_to_close <= 0:
            self._logger.info("Конец торгового дня, закрываем позиции")
            await self._close_all_positions()
            return True
        await self._check_close_warnings(time_to_close, set())
        return False

    async def _process_new_candles_tick(self) -> None:
        candles = await self._get_new_candles()
        if candles:
            await self._process_candles(candles)
        await self._update_stats()

    async def run_trading_loop(self) -> None:
        """Запускает основной торговый цикл"""
        if not self._is_running:
            self._logger.error("Сессия не запущена")
            return
        
        self._logger.info("Запуск торгового цикла...")
        
        try:
            while self._is_running:
                try:
                    if await self._maybe_close_positions_eod():
                        break
                    await self._process_new_candles_tick()
                    await asyncio.sleep(1)
                except Exception as e:
                    error_msg = str(e)
                    if "CANCELLED" in error_msg or "RST_STREAM" in error_msg:
                        await self._handle_grpc_cancelled(error_msg)
                    else:
                        await self._handle_generic_error_with_recovery(e)
        except KeyboardInterrupt:
            self._logger.info("Получен сигнал остановки")
            await self.stop()
        except Exception as e:
            self._logger.error(f"Критическая ошибка в торговом цикле: {e}")
            await self.stop()
    
    async def _check_market_status(self) -> bool:
        """Проверяет статус рынка с поддержкой выходных торгов"""
        if self._force_start:
            self._logger.info("Принудительный запуск (игнорируем статус рынка)")
            return True
        
        try:
            # Используем расширенную проверку с поддержкой выходных торгов
            market_status = await get_market_status_enhanced()
            
            if market_status.get('is_trading'):
                session_type = market_status.get('session_type', 'unknown')
                message = market_status.get('message', 'Рынок открыт')
                self._logger.info(f"Рынок открыт ({session_type}): {message}")
                return True
            else:
                reason = market_status.get('message') or f"{market_status.get('session_type','unknown')} (нет message)"
                self._logger.info(f"Рынок закрыт: {reason}")
                
                # Ждем открытия рынка
                await self._wait_for_market_open()
                return True
                
        except Exception as e:
            self._logger.error(f"Ошибка проверки статуса рынка: {e}")
            self._logger.info("Пауза торговли до восстановления API...")
            
            # Ждем восстановления API
            await self._wait_for_api_recovery()
            return True
    
    async def _wait_for_market_open(self) -> None:
        """Ждет открытия рынка"""
        self._logger.info("Ожидание открытия рынка...")
        
        while True:
            try:
                market_status = await get_market_status_with_api()
                
                if market_status.get('is_trading'):
                    self._logger.info("Рынок открылся!")
                    break
                else:
                    reason = market_status.get('message') or f"{market_status.get('session_type','unknown')} (no message)"
                    self._logger.info(f"Рынок закрыт: {reason}")
                    await asyncio.sleep(60)  # Проверяем каждую минуту
                    
            except Exception as e:
                self._logger.error(f"Ошибка при ожидании открытия рынка: {e}")
                self._logger.info("Пауза торговли до восстановления API...")
                
                # Ждем восстановления API
                await self._wait_for_api_recovery()
                break
            except asyncio.CancelledError:
                self._logger.info("Ожидание открытия рынка прервано")
                return
    
    async def _wait_for_api_recovery(self) -> None:
        """Ждет восстановления API"""
        self._logger.info("Ожидание восстановления API...")
        
        while True:
            try:
                # Проверяем доступность API
                market_status = await get_market_status_with_api()
                self._logger.info("API восстановлен!")
                break
                
            except Exception as e:
                self._logger.warning(f"API все еще недоступен: {e}")
                self._logger.info("Продолжаем ожидание...")
                await asyncio.sleep(30)  # Проверяем каждые 30 секунд
            except asyncio.CancelledError:
                self._logger.info("Ожидание восстановления API прервано")
                return
    
    async def _get_time_to_close(self) -> int:
        """
        Получает время до закрытия позиций в секундах
        
        Returns:
            Количество секунд до времени закрытия (0 или отрицательное = время закрыть)
        """
        try:
            
            # Получаем текущее время в Москве
            moscow_tz = pytz.timezone('Europe/Moscow')
            now = datetime.now(moscow_tz)
            
            # Создаем время закрытия на сегодня
            close_datetime = moscow_tz.localize(
                datetime.combine(now.date(), self._config.close_time)
            )
            
            # Если время закрытия уже прошло сегодня, берем завтра
            if now >= close_datetime:
                close_datetime = moscow_tz.localize(
                    datetime.combine(now.date() + timedelta(days=1), self._config.close_time)
                )
            
            # Вычисляем разность в секундах
            time_diff = (close_datetime - now).total_seconds()
            return int(time_diff)
            
        except Exception as e:
            self._logger.error(f"Ошибка вычисления времени до закрытия: {e}")
            return 0  # В случае ошибки считаем, что время закрыть
    
    async def _check_close_warnings(self, time_to_close: int, shown_warnings: set) -> None:
        """
        Проверяет и показывает предупреждения о скором закрытии позиций
        
        Args:
            time_to_close: Время до закрытия в секундах
            shown_warnings: Множество уже показанных предупреждений
        """
        for warning_period in self._config.warning_periods:
            if time_to_close <= warning_period and warning_period not in shown_warnings:
                # Показываем предупреждение
                minutes = warning_period // 60
                seconds = warning_period % 60
                
                if minutes > 0:
                    message = f"До закрытия позиций осталось {minutes} минут"
                    if seconds > 0:
                        message += f" {seconds} секунд"
                else:
                    message = f"До закрытия позиций осталось {seconds} секунд"
                
                self._logger.warning(message)
                shown_warnings.add(warning_period)
                break  # Показываем только одно предупреждение за раз
    
    async def _get_new_candles(self) -> list:
        """Получает новые свечи"""
        try:
            candles = await self._dependencies.market_data_stream.get_latest_candles()
            # Отправляем свечи в визуализатор
            if self._visualizer and candles:
                for candle in candles:
                    candle_data = {
                        'time': candle.time,
                        'open': candle.open.units + candle.open.nano / 1_000_000_000,
                        'high': candle.high.units + candle.high.nano / 1_000_000_000,
                        'low': candle.low.units + candle.low.nano / 1_000_000_000,
                        'close': candle.close.units + candle.close.nano / 1_000_000_000,
                        'volume': candle.volume
                    }
                    await self._visualizer.add_candle(candle_data)
            return candles
        except Exception as e:
            self._logger.error(f"Ошибка получения свечей: {e}")
            return []
    
    async def _process_candles(self, candles: list) -> None:
        """Обрабатывает свечи через стратегии"""
        try:
            for candle in candles:
                # Обрабатываем свечу через стратегии
                signals = await self._dependencies.strategy_manager.on_candle(candle)
                
                # Отправляем сигналы в визуализатор
                if self._visualizer and signals:
                    for signal in signals:
                        signal_data = {
                            'time': signal.time,
                            'type': signal.type,
                            'price': signal.price,
                            'reason': getattr(signal, 'reason', ''),
                            'strategy': getattr(signal, 'strategy', ''),
                            'quantity': getattr(signal, 'quantity', 1),
                            'strength': getattr(signal, 'strength', 0.0)
                        }
                        await self._visualizer.add_signal(signal_data)
                
                # Обновляем статистику
                self._stats.add_signal()
                
        except Exception as e:
            self._logger.error(f"Ошибка обработки свечей: {e}")
    
    async def _close_all_positions(self) -> None:
        """Закрывает все открытые позиции через StrategyManager"""
        self._logger.info("Закрытие всех позиций...")
        
        try:
            # Закрываем позиции через StrategyManager
            await self._dependencies.strategy_manager.close_all_positions()
            
            self._logger.info("Все позиции закрыты")
            
        except Exception as e:
            self._logger.error(f"Ошибка при закрытии позиций: {e}")
    
    async def _update_stats(self) -> None:
        """Обновляет статистику сессии"""
        try:
            # Получаем текущий баланс
            portfolio = await self._dependencies.portfolio_manager.get_portfolio()
            current_balance = portfolio.total_amount
            
            # Обновляем только статистику баланса
            self._stats.update_balance(current_balance)
            
            # Обновляем статус стратегий
            try:
                strategy_status = "Стратегии работают нормально"
                dm = self._dependencies.data_manager
                if dm:
                    dm.update_strategy_status(strategy_status)
            except Exception as e:
                self._logger.error(f"Ошибка обновления статуса стратегий: {e}")
            
        except Exception as e:
            self._logger.error(f"Ошибка обновления статистики: {e}")
    
    async def _log_session_info(self) -> None:
        """Логирует информацию о сессии"""
        self._logger.info("=== ИНФОРМАЦИЯ О СЕССИИ ===")
        self._logger.info(f"FIGI: {self.config.figi}")
        self._logger.info(f"Автозакрытие позиций: {self.config.auto_close_positions}")
        self._logger.info(f"Принудительный запуск: {self.force_start}")
        self._logger.info(f"Время запуска: {self._stats.start_time}")
        
        # Обновляем статус стратегий в визуализаторе
        dm = self._dependencies.data_manager
        if dm:
            try:
                strategy_status = "Стратегии активны и готовы к торговле"
                dm.update_strategy_status(strategy_status)
                self._logger.info("Статус стратегий обновлен в визуализаторе")
            except Exception as e:
                self._logger.error(f"Ошибка обновления статуса стратегий: {e}")
    
    async def get_session_status(self) -> dict:
        """Возвращает статус сессии"""
        return {
            'is_running': self._is_running,
            'is_initialized': self._is_initialized,
            'stats': self._stats.get_stats_dict()
        }
