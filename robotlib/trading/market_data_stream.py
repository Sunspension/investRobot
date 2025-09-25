"""
Модуль для работы со стримом рыночных данных
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional, List
from tinkoff.invest import Candle, HistoricCandle, CandleInterval
from tinkoff.invest.market_data_stream.async_market_data_stream_manager import AsyncMarketDataStreamManager

from robotlib.utils.logger import get_logger
from robotlib.trading.interfaces import TinkoffAPIClientable, MarketDataStreamable
from robotlib.trading_interfaces import CandleEventSinkable
from robotlib.utils.backoff import compute_backoff_delay
from tinkoff.invest import MarketDataRequest, SubscribeCandlesRequest, CandleInstrument, SubscriptionAction

# Импортируем новые компоненты
from robotlib.trading.candle_cache_interfaces import CandleCacheable
from robotlib.trading.stream_watchdog import StreamWatchdog
from robotlib.trading.historical_data_loader_interfaces import HistoricalDataLoaderable


class TinkoffStreamAdapter:
    """
    Адаптер для AsyncMarketDataStreamManager - убирает путаницу с названиями
    
    Проблема: AsyncMarketDataStreamManager из библиотеки Tinkoff имеет вводящее в заблуждение
    название - не все его методы асинхронные. Например, stop() и subscribe() - синхронные.
    
    Решение: Создаем адаптер с понятными названиями методов, которые четко указывают
    на их синхронную/асинхронную природу.
    """
    
    def __init__(self, stream_manager: AsyncMarketDataStreamManager):
        self._stream_manager = stream_manager
        self._logger = get_logger(__name__)
    
    def subscribe(self, request) -> None:
        """Подписывается на данные (синхронный метод)"""
        self._stream_manager.subscribe(request)
    
    def stop(self) -> None:
        """Останавливает стрим (синхронный метод)"""
        self._stream_manager.stop()
    
    def __aiter__(self):
        """Асинхронный итератор для получения данных"""
        return self._stream_manager.__aiter__()
    
    def __iter__(self):
        """Синхронный итератор для получения данных"""
        return self._stream_manager.__iter__()


class MarketDataStream(MarketDataStreamable):
    """Класс для управления стримом рыночных данных"""
    
    def __init__(
        self, 
        api_client: TinkoffAPIClientable, 
        figi: str = "FUTIMOEXF000",
        *,
        candle_cache: CandleCacheable,
        historical_loader: HistoricalDataLoaderable,
        watchdog: Optional[StreamWatchdog] = None,
    ):
        """
        Инициализация стрима рыночных данных
        
        Args:
            api_client: API клиент для создания стрима
            figi: FIGI инструмента для подписки
            candle_cache: Кэш для свечей
            historical_loader: Загрузчик исторических данных
            watchdog: Монитор состояния стрима (опционально)
        """
        self._api_client = api_client
        self._figi = figi
        self._logger = get_logger(__name__)
        
        # Используем переданные компоненты
        self._candle_cache = candle_cache
        self._historical_loader = historical_loader
        self._watchdog = watchdog
        
        # Callback система
        self._candle_callbacks: List[Callable[[Candle], None]] = []
        self._signal_callbacks: List[Callable] = []
        
        # Состояние стрима
        self._stream_adapter: Optional[TinkoffStreamAdapter] = None
        self._is_running = False
        self._sink: Optional[CandleEventSinkable] = None

    def set_event_sink(self, sink: CandleEventSinkable) -> None:
        """Устанавливает приемник событий (candle/signal/market_status)."""
        self._sink = sink
    
    @property
    def figi(self) -> str:
        """FIGI инструмента для подписки"""
        return self._figi
    
    @property
    def is_running(self) -> bool:
        """Флаг работы стрима"""
        return self._is_running
    
    @property
    def current_price(self) -> Optional[float]:
        """Текущая цена"""
        return self._candle_cache.get_current_price()
    
    def _is_api_client_ready(self) -> bool:
        """Проверяет, готов ли API клиент к использованию"""
        return (
            self._api_client is not None and 
            self._api_client.services is not None
        )
    
    async def start(self) -> bool:
        """
        Запускает стрим рыночных данных
        
        Returns:
            True если стрим запущен успешно, False иначе
        """
        try:
            self._logger.info(f"Запуск стрима рыночных данных для {self._figi}")
            
            # Проверяем, что API клиент готов
            if not self._is_api_client_ready():
                self._logger.error("API клиент не инициализирован")
                return False
            
            # Создаем стрим менеджер
            raw_stream_manager = await self._api_client.create_market_data_stream()
            
            # Проверяем, что стрим менеджер создан
            if raw_stream_manager is None:
                self._logger.error("Не удалось создать стрим менеджер")
                return False
            
            # Создаем адаптер для убирания путаницы с названиями
            self._stream_adapter = TinkoffStreamAdapter(raw_stream_manager)
            
            # Gap-fill: если у нас есть последняя свеча, дозаполним пропуски REST'ом
            try:
                if self._watchdog and self._watchdog.last_candle_time is not None:
                    asyncio.create_task(self._historical_loader.gap_fill_missing_candles(
                        self._watchdog.last_candle_time, self._sink
                    ))
            except Exception:
                pass
            
            # Всегда подписываемся на поток свечей, независимо от статуса рынка
            try:
                request = MarketDataRequest(
                    subscribe_candles_request=SubscribeCandlesRequest(
                        subscription_action=SubscriptionAction.SUBSCRIPTION_ACTION_SUBSCRIBE,
                        instruments=[
                            CandleInstrument(
                                figi=self._figi,
                                interval=CandleInterval.CANDLE_INTERVAL_1_MIN
                            )
                        ]
                    )
                )
                self._stream_adapter.subscribe(request)
                self._logger.info("Подписка на поток свечей активирована (независимо от статуса рынка)")
            except Exception as e:
                self._logger.error(f"Ошибка подписки на поток свечей: {e}")
                # В фоне попробуем подгрузить историю, чтобы не было пусто
                self._is_running = True
                asyncio.create_task(self._load_historical_data())
                return True

            # Запускаем обработку данных
            self._is_running = True
            asyncio.create_task(self._process_stream())
            
            # Запускаем watchdog, если он включен
            if self._watchdog:
                # Устанавливаем callback для перезапуска
                self._watchdog.set_restart_callback(self._restart_stream)
                asyncio.create_task(self._watchdog.start_monitoring())
            
            self._logger.info("Стрим рыночных данных запущен")
            return True
            
        except Exception as e:
            self._logger.error(f"Ошибка запуска стрима: {e}")
            return False
    
    async def stop(self) -> None:
        """Останавливает стрим рыночных данных"""
        if not self._is_running:
            return
            
        try:
            self._logger.info("Остановка стрима рыночных данных")
            
            self._is_running = False
            
            # Останавливаем watchdog
            if self._watchdog:
                await self._watchdog.stop_monitoring()
            
            if self._stream_adapter is not None:
                try:
                    # Просто вызываем stop() синхронно
                    self._stream_adapter.stop()
                except Exception as e:
                    self._logger.warning(f"Ошибка остановки стрим адаптера: {e}")
                finally:
                    self._stream_adapter = None
            
            self._logger.info("Стрим рыночных данных остановлен")
            
        except Exception as e:
            self._logger.error(f"Ошибка остановки стрима: {e}")
    
    def _restart_stream(self) -> None:
        """Перезапускает стрим (используется watchdog'ом)"""
        try:
            self._logger.info("Перезапуск стрима по требованию watchdog")
            if self._stream_adapter is not None:
                self._stream_adapter.stop()
            self._is_running = False
            # Создаем задачу для перезапуска
            asyncio.create_task(self._async_restart())
        except Exception as e:
            self._logger.error(f"Ошибка перезапуска стрима: {e}")
    
    async def _async_restart(self) -> None:
        """Асинхронный перезапуск стрима"""
        try:
            await asyncio.sleep(1)
            await self.start()
        except Exception as e:
            self._logger.error(f"Ошибка асинхронного перезапуска: {e}")
    
    def reset(self) -> None:
        """Сбрасывает флаг остановки для возможности перезапуска"""
        self._is_running = False
    
    
    async def _process_stream(self) -> None:
        """Обрабатывает данные из стрима"""
        try:
            while self._is_running and self._stream_adapter:
                try:
                    # Получаем данные из стрима
                    async for market_data in self._stream_adapter:
                        if not self._is_running:
                            break
                        # Обрабатываем свечи
                        if market_data.candle:
                            self._process_candle(market_data.candle)
                        # Обрабатываем другие типы данных
                        if market_data.trade:
                            await self._process_trade(market_data.trade)
                        if market_data.orderbook:
                            await self._process_orderbook(market_data.orderbook)
                            
                except Exception as stream_error:
                    # Обрабатываем ошибки стрима: везде пытаемся переподключиться
                    self._logger.warning(f"Ошибка/отмена стрима: {stream_error}")
                    retries = 0
                    # Отключаем текущий цикл обработки
                    self._is_running = True  # позволяем циклу переподключений работать
                    # Gap-fill перед попыткой реконнекта (асинхронно)
                    try:
                        if self._watchdog and self._watchdog.last_candle_time is not None:
                            asyncio.create_task(self._historical_loader.gap_fill_missing_candles(
                                self._watchdog.last_candle_time, self._sink
                            ))
                    except Exception:
                        pass
                    while self._is_running:
                        delay = compute_backoff_delay(retries, base_seconds=0.5, max_seconds=30.0, jitter="full")
                        self._logger.info(f"Повторное подключение через {delay:.2f}с (попытка {retries+1})")
                        await asyncio.sleep(delay)
                        try:
                            ok = await self.start()
                            if ok:
                                self._logger.info("Переподключение успешно")
                                return
                        except Exception as e:
                            self._logger.warning(f"Не удалось переподключиться: {e}")
                        retries += 1
                    break
                        
        except Exception as e:
            self._logger.error(f"Ошибка обработки стрима: {e}")
            self._is_running = False
    
    def _process_candle(self, candle: Candle) -> None:
        """
        Обрабатывает полученную свечу
        
        Args:
            candle: Свеча от API
        """
        try:
            if not isinstance(candle, (Candle, HistoricCandle)):
                self._logger.debug("Получено не-свечное сообщение, пропускаем")
                return
                
            # Проверяем, что свеча для нашего инструмента
            candle_figi = getattr(candle, 'figi', self._figi)
            if candle_figi != self._figi:
                return
            
            # Добавляем свечу в кэш
            self._candle_cache.add_candle(candle)
            
            # Обновляем время последней свечи для watchdog
            try:
                lc_time = getattr(candle, 'time', None)
                if lc_time is None:
                    last_candle_time = datetime.now(timezone.utc)
                else:
                    if getattr(lc_time, 'tzinfo', None) is None:
                        last_candle_time = lc_time.replace(tzinfo=timezone.utc)
                    else:
                        last_candle_time = lc_time.astimezone(timezone.utc)
                
                # Обновляем watchdog
                if self._watchdog:
                    self._watchdog.set_last_candle_time(last_candle_time)
                    
            except Exception:
                if self._watchdog:
                    self._watchdog.set_last_candle_time(datetime.now(timezone.utc))
            
            # Логируем получение свечи
            figi_info = getattr(candle, 'figi', self._figi)
            current_price = self._candle_cache.get_current_price()
            self._logger.debug(f"Получена свеча: {candle.time} - {current_price} (FIGI: {figi_info})")
            
            # Публикуем свечу в приемник
            try:
                if self._sink is not None:
                    asyncio.create_task(self._sink.on_candle(candle, current_price or 0.0, self._figi))
            except Exception as pub_err:
                self._logger.warning(f"Не удалось отправить свечу в визуализатор: {pub_err}")
            
            # Вызываем колбэки для свечей
            for callback in self._candle_callbacks:
                try:
                    callback(candle)
                except Exception as e:
                    self._logger.error(f"Ошибка в колбэке свечи: {e}")
                        
        except Exception as e:
            self._logger.error(f"Ошибка обработки свечи: {e}")
    
    async def _process_trade(self, trade) -> None:
        """Обрабатывает сделку"""
        # Пока что просто логируем
        self._logger.debug(f"Получена сделка: {trade}")
    
    async def _process_orderbook(self, orderbook) -> None:
        """Обрабатывает стакан заявок"""
        # Пока что просто логируем
        self._logger.debug(f"Получен стакан: {orderbook}")

    
    def add_candle_callback(self, callback: Callable[[Candle], None]) -> None:
        """
        Добавляет колбэк для обработки свечей
        
        Args:
            callback: Функция для обработки свечей
        """
        self._candle_callbacks.append(callback)
    
    def add_signal_callback(self, callback: Callable) -> None:
        """
        Добавляет колбэк для обработки сигналов
        
        Args:
            callback: Функция для обработки сигналов
        """
        self._signal_callbacks.append(callback)
    
    def remove_candle_callback(self, callback: Callable[[Candle], None]) -> None:
        """Удаляет колбэк для свечей"""
        if callback in self._candle_callbacks:
            self._candle_callbacks.remove(callback)
    
    def remove_signal_callback(self, callback: Callable) -> None:
        """Удаляет колбэк для сигналов"""
        if callback in self._signal_callbacks:
            self._signal_callbacks.remove(callback)
    
    async def get_latest_candles(self, count: int = 10) -> List[Candle]:
        """
        Возвращает последние N свечей из кэша
        
        Args:
            count: Количество свечей для возврата
            
        Returns:
            Список последних свечей
        """
        return self._candle_cache.get_latest_candles(count)
    
    async def get_current_price(self) -> Optional[float]:
        """
        Возвращает текущую цену
        
        Returns:
            Текущая цена или None если данных нет
        """
        return self._candle_cache.get_current_price()
    
    def get_cached_candles(self) -> List[Candle]:
        """
        Возвращает все кэшированные свечи
        
        Returns:
            Список всех кэшированных свечей
        """
        return self._candle_cache.get_cached_candles()
    
    def get_cache_size(self) -> int:
        """
        Возвращает размер кэша
        
        Returns:
            Количество свечей в кэше
        """
        return self._candle_cache.get_cache_size()
    
    def clear_cache(self) -> None:
        """Очищает кэш свечей"""
        self._candle_cache.clear_cache()
    
    async def _load_historical_data(self) -> None:
        """Загружает исторические данные фиксированного окна до текущего момента (UTC)."""
        try:
            self._logger.info("Загрузка исторических данных (фиксированное окно)")
            now_utc = datetime.now(timezone.utc)
            from_date = now_utc - timedelta(hours=4)
            to_date = now_utc
            
            # Логируем параметры запроса
            self._logger.info(f"🔍 Параметры запроса свечей:")
            self._logger.info(f"🔍 FIGI: {self._figi}")
            self._logger.info(f"🔍 from_date: {from_date} (тип: {type(from_date)})")
            self._logger.info(f"🔍 to_date: {to_date} (тип: {type(to_date)})")
            
            # Используем HistoricalDataLoader
            candles = await self._historical_loader.load_historical_data(from_date, to_date)
            
            if candles:
                self._logger.info(f"Загружено {len(candles)} исторических свечей")
                
                # Логируем период данных для отладки
                if candles:
                    first_candle = candles[0]
                    last_candle = candles[-1]
                    self._logger.info(f"Период данных: {first_candle.time} - {last_candle.time}")
                
                # Обрабатываем каждую свечу
                for candle in candles:
                    self._process_candle(candle)
            else:
                self._logger.warning("Не удалось загрузить исторические данные")
                
        except Exception as e:
            self._logger.error(f"Ошибка загрузки исторических данных: {e}")
    
    async def _get_last_main_trading_session_period(self) -> tuple:
        """
        Определяет период последней основной торговой сессии (10:00-18:45)
        
        Returns:
            tuple: (from_date, to_date) - период последней основной торговой сессии
        """
        return await self._historical_loader.get_last_main_trading_session_period()
    
    async def _get_last_trading_session_period(self) -> tuple:
        """
        Определяет период последней торговой сессии
        
        Returns:
            tuple: (from_date, to_date) - период последней торговой сессии
        """
        return await self._historical_loader.get_last_trading_session_period()
