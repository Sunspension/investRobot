"""
Модуль для работы со стримом рыночных данных
"""
import asyncio
from datetime import datetime, timedelta, timezone, time
from typing import Callable, Optional, List
from collections import deque
import pytz
from tinkoff.invest import Candle, HistoricCandle, CandleInterval
from tinkoff.invest.market_data_stream.async_market_data_stream_manager import AsyncMarketDataStreamManager

from robotlib.utils.logger import get_logger
from robotlib.utils.market_hours_enhanced import get_market_status_enhanced
from robotlib.utils.tinkoff_market_hours import get_tinkoff_market_hours
from robotlib.trading.interfaces import TinkoffAPIClientable, MarketDataStreamable
from robotlib.visualization_interfaces import TradingEventSinkable
from robotlib.utils.backoff import compute_backoff_delay
from tinkoff.invest import MarketDataRequest, SubscribeCandlesRequest, CandleInstrument, SubscriptionAction
from robotlib.utils.market_hours_enhanced import get_market_status_enhanced
from robotlib.utils.money import Money


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
        cache_size: int = 100,
        *,
        watchdog_enabled: bool,
        watchdog_stale_seconds: int,
        watchdog_require_open_market: bool,
    ):
        """
        Инициализация стрима рыночных данных
        
        Args:
            api_client: API клиент для создания стрима
            signal_manager: Менеджер сигналов для обработки свечей
            figi: FIGI инструмента для подписки
            cache_size: Размер кэша для хранения свечей
        """
        self._api_client = api_client
        self._figi = figi
        self._cache_size = cache_size
        
        # Создаем системные объекты
        self._cached_candles = deque(maxlen=cache_size)
        self._logger = get_logger(__name__)
        self._candle_callbacks: List[Callable[[Candle], None]] = []
        self._signal_callbacks: List[Callable] = []
        
        self._stream_adapter: Optional[TinkoffStreamAdapter] = None
        self._is_running = False
        self._current_price: Optional[float] = None
        self._sink: Optional[TradingEventSinkable] = None
        self._last_candle_at: Optional[datetime] = None
        self._watchdog_enabled = watchdog_enabled
        self._watchdog_stale_seconds = watchdog_stale_seconds
        self._watchdog_require_open_market = watchdog_require_open_market

    def set_event_sink(self, sink: TradingEventSinkable) -> None:
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
        return self._current_price
    
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
                if self._last_candle_at is not None:
                    asyncio.create_task(self._gap_fill_missing_candles())
            except Exception:
                pass
            
            # Проверяем статус рынка (расширенная логика с типом сессии и таймерами)
            market_status = await get_market_status_enhanced()
            # Публикуем изменение статуса рынка
            try:
                status_payload = {
                    'is_trading': market_status.get('is_trading', False),
                    'session_type': market_status.get('session_type', 'unknown'),
                    'current_time': market_status.get('current_time'),
                    'next_session': market_status.get('next_session'),
                    'time_until_next': market_status.get('time_until_next')
                }
                if self._sink is not None:
                    asyncio.create_task(self._sink.on_market_status(status_payload))
                self._logger.info(f"Опубликован статус рынка: is_trading={market_status.get('is_trading', False)}")
            except Exception as publish_error:
                self._logger.warning(f"Не удалось опубликовать статус рынка: {publish_error}")
            
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
            # Запускаем сторож, чтобы восстановиться при тишине потока (по конфигу)
            if self._watchdog_enabled:
                asyncio.create_task(self._watchdog_stale_stream(self._watchdog_stale_seconds))
            
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
    
    def reset(self) -> None:
        """Сбрасывает флаг остановки для возможности перезапуска"""
        self._is_running = False
    
    async def _gap_fill_missing_candles(self) -> None:
        """Дозагружает недостающие свечи с момента последней полученной до текущего времени.
        
        Использует REST-метод get_candles, публикует их через sink.on_candle, сохраняя семантику пайплайна.
        """
        try:
            if self._last_candle_at is None:
                return
            # Нормализуем к aware-UTC и сдвигаем старт на +1с, чтобы избежать дубликата
            from_time = self._last_candle_at
            if getattr(from_time, 'tzinfo', None) is None:
                from_time = from_time.replace(tzinfo=timezone.utc)
            else:
                from_time = from_time.astimezone(timezone.utc)
            from_time = from_time + timedelta(seconds=1)
            to_time = datetime.now(timezone.utc)
            # Защитимся от некорректного порядка
            if to_time <= from_time:
                return
            candles = await self._api_client.get_candles(
                self._figi,
                from_time,
                to_time,
                CandleInterval.CANDLE_INTERVAL_1_MIN,
            )
            if not candles:
                return
            # Преобразуем и публикуем через sink для единообразия (и записи в БД, если sink=DBIngestionSink)
            for c in candles:
                try:
                    # Расчет цены как в stream-пути
                    price = float(getattr(c.close, 'units', 0) + getattr(c.close, 'nano', 0) / 1e9)
                except Exception:
                    try:
                        price = Money(c.close).to_float()
                    except Exception:
                        price = 0.0
                if self._sink is not None:
                    asyncio.create_task(self._sink.on_candle(c, price, self._figi))
            self._logger.info(f"Gap-fill: дозагружено {len(candles)} свечей с {from_time} по {to_time}")
        except Exception as e:
            self._logger.warning(f"Gap-fill: ошибка дозагрузки свечей: {e}")
    
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
                        asyncio.create_task(self._gap_fill_missing_candles())
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
            
            # Обновляем кэш и текущую цену
            self._cached_candles.append(candle)
            self._current_price = candle.close.units + candle.close.nano / 1_000_000_000
            # Сохраняем время последней свечи как aware-UTC (fallback: now UTC)
            try:
                lc_time = getattr(candle, 'time', None)
                if lc_time is None:
                    self._last_candle_at = datetime.now(timezone.utc)
                else:
                    if getattr(lc_time, 'tzinfo', None) is None:
                        self._last_candle_at = lc_time.replace(tzinfo=timezone.utc)
                    else:
                        self._last_candle_at = lc_time.astimezone(timezone.utc)
            except Exception:
                self._last_candle_at = datetime.now(timezone.utc)
            
            # Логируем получение свечи
            figi_info = getattr(candle, 'figi', self._figi)
            self._logger.debug(f"Получена свеча: {candle.time} - {self._current_price} (FIGI: {figi_info})")
            
            # Публикуем свечу в визуализатор
            try:
                if self._sink is not None:
                    asyncio.create_task(self._sink.on_candle(candle, self._current_price or 0.0, self._figi))
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

    async def _watchdog_stale_stream(self, stale_seconds: int = 120) -> None:
        """Перезапускает стрим, если не приходят свечи более stale_seconds."""
        try:
            while self._is_running:
                await asyncio.sleep(30)
                if not self._is_running:
                    break
                if self._last_candle_at is None:
                    continue
                if (datetime.now() - self._last_candle_at).total_seconds() > stale_seconds:
                    # Опционально: перезапускать только в торговые часы
                    if self._watchdog_require_open_market:
                        try:
                            status = await get_market_status_enhanced()
                            if not bool(status.get('is_trading', False)):
                                self._logger.info(
                                    f"Watchdog: тишина > {stale_seconds}с, рынок закрыт — перезапуск пропущен"
                                )
                                continue
                        except Exception:
                            # В случае ошибки проверки — позволяем перезапуск для надежности
                            pass
                    self._logger.warning(f"Watchdog: тишина > {stale_seconds}с — перезапуск стрима")
                    try:
                        if self._stream_adapter is not None:
                            self._stream_adapter.stop()
                    except Exception:
                        pass
                    self._is_running = False
                    await asyncio.sleep(1)
                    await self.start()
                    return
        except Exception:
            pass
    
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
        try:
            if not self._cached_candles:
                self._logger.warning("Кэш свечей пуст")
                return []
            
            # Возвращаем последние count свечей
            return list(self._cached_candles)[-count:]
            
        except Exception as e:
            self._logger.error(f"Ошибка получения последних свечей: {e}")
            return []
    
    async def get_current_price(self) -> Optional[float]:
        """
        Возвращает текущую цену
        
        Returns:
            Текущая цена или None если данных нет
        """
        return self._current_price
    
    def get_cached_candles(self) -> List[Candle]:
        """
        Возвращает все кэшированные свечи
        
        Returns:
            Список всех кэшированных свечей
        """
        return list(self._cached_candles)
    
    def get_cache_size(self) -> int:
        """
        Возвращает размер кэша
        
        Returns:
            Количество свечей в кэше
        """
        return len(self._cached_candles)
    
    def clear_cache(self) -> None:
        """Очищает кэш свечей"""
        self._cached_candles.clear()
        self._current_price = None
    
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
            self._logger.info(f"🔍 interval: {CandleInterval.CANDLE_INTERVAL_1_MIN}")
            
            # Получаем исторические свечи
            candles_response = await self._api_client.get_candles(
                figi=self._figi,
                from_date=from_date,
                to_date=to_date,
                interval=CandleInterval.CANDLE_INTERVAL_1_MIN
            )
            
            if candles_response and candles_response.candles:
                self._logger.info(f"Загружено {len(candles_response.candles)} исторических свечей")
                
                # Логируем период данных для отладки
                if candles_response.candles:
                    first_candle = candles_response.candles[0]
                    last_candle = candles_response.candles[-1]
                    self._logger.info(f"Период данных: {first_candle.time} - {last_candle.time}")
                
                # Обрабатываем каждую свечу
                for candle in candles_response.candles:
                    self._process_candle(candle)
                    
            else:
                self._logger.warning(f"Не удалось загрузить исторические данные. Ответ: {candles_response}")
                if candles_response:
                    self._logger.warning(f"Тип ответа: {type(candles_response)}")
                    if hasattr(candles_response, 'candles'):
                        self._logger.warning(f"Свечи в ответе: {candles_response.candles}")
                
        except Exception as e:
            self._logger.error(f"Ошибка загрузки исторических данных: {e}")
    
    async def _get_last_main_trading_session_period(self) -> tuple:
        """
        Определяет период последней основной торговой сессии (10:00-18:45)
        
        Returns:
            tuple: (from_date, to_date) - период последней основной торговой сессии
        """
        try:
            market_hours = await get_tinkoff_market_hours()
            schedule = await market_hours.get_trading_schedule()
            
            # Получаем текущую дату
            current_date = datetime.now(market_hours.moscow_tz).date()
            
            # Ищем последний торговый день
            last_trading_day = None
            for i in range(7):  # Проверяем последние 7 дней
                check_date = current_date - timedelta(days=i)
                date_str = check_date.isoformat()
                
                # Проверяем разные форматы дат
                search_keys = [
                    f"{date_str}T00:00:00+00:00",
                    date_str
                ]
                
                for key in search_keys:
                    if key in schedule['days']:
                        day_info = schedule['days'][key]
                        if day_info['is_trading_day'] and day_info['sessions']:
                            last_trading_day = day_info
                            break
                
                if last_trading_day:
                    break
            
            if last_trading_day and last_trading_day['sessions']:
                # Берем основную сессию (первую) - 10:00-18:45
                main_session = last_trading_day['sessions'][0]
                
                # Конвертируем время в московское
                if main_session['start'].tzinfo:
                    session_start = main_session['start'].astimezone(market_hours.moscow_tz)
                    session_end = main_session['end'].astimezone(market_hours.moscow_tz)
                else:
                    session_start = market_hours.moscow_tz.localize(main_session['start'])
                    session_end = market_hours.moscow_tz.localize(main_session['end'])
                
                # Для фьючерсов используем только основную сессию (10:00-18:45)
                # Принудительно устанавливаем время основной сессии
                session_date = session_start.date()
                from_date = market_hours.moscow_tz.localize(
                    datetime.combine(session_date, time(10, 0))
                )
                to_date = market_hours.moscow_tz.localize(
                    datetime.combine(session_date, time(18, 45))
                )
                
                self._logger.info(f"Основная сессия для фьючерса: {from_date} - {to_date}")
                return from_date, to_date
            else:
                # Если не найдена торговая сессия, используем стандартное время MOEX
                self._logger.warning("Не найдена торговая сессия, используем стандартное время MOEX (10:00-18:45)")
                yesterday = current_date - timedelta(days=1)
                from_date = market_hours.moscow_tz.localize(
                    datetime.combine(yesterday, time(10, 0))
                )
                to_date = market_hours.moscow_tz.localize(
                    datetime.combine(yesterday, time(18, 45))
                )
                return from_date, to_date
                
        except Exception as e:
            self._logger.error(f"Ошибка определения периода основной сессии: {e}")
            # Fallback на вчерашний день
            moscow_tz = pytz.timezone('Europe/Moscow')
            yesterday = datetime.now(moscow_tz).date() - timedelta(days=1)
            from_date = moscow_tz.localize(datetime.combine(yesterday, time(10, 0)))
            to_date = moscow_tz.localize(datetime.combine(yesterday, time(18, 45)))
            return from_date, to_date
    
    async def _get_last_trading_session_period(self) -> tuple:
        """
        Определяет период последней торговой сессии
        
        Returns:
            tuple: (from_date, to_date) - период последней торговой сессии
        """
        try:
            market_hours = await get_tinkoff_market_hours()
            schedule = await market_hours.get_trading_schedule()
            
            # Получаем текущую дату
            current_date = datetime.now(market_hours.moscow_tz).date()
            
            # Ищем последний торговый день
            last_trading_day = None
            for i in range(7):  # Проверяем последние 7 дней
                check_date = current_date - timedelta(days=i)
                date_str = check_date.isoformat()
                
                # Проверяем разные форматы дат
                search_keys = [
                    f"{date_str}T00:00:00+00:00",
                    date_str
                ]
                
                for key in search_keys:
                    if key in schedule['days']:
                        day_info = schedule['days'][key]
                        if day_info['is_trading_day'] and day_info['sessions']:
                            last_trading_day = day_info
                            break
                
                if last_trading_day:
                    break
            
            if last_trading_day and last_trading_day['sessions']:
                # Берем основную сессию (первую)
                main_session = last_trading_day['sessions'][0]
                
                # Конвертируем время в московское
                if main_session['start'].tzinfo:
                    session_start = main_session['start'].astimezone(market_hours.moscow_tz)
                    session_end = main_session['end'].astimezone(market_hours.moscow_tz)
                else:
                    session_start = main_session['start'].replace(tzinfo=timezone.utc).astimezone(market_hours.moscow_tz)
                    session_end = main_session['end'].replace(tzinfo=timezone.utc).astimezone(market_hours.moscow_tz)
                
                self._logger.info(f"Найдена последняя торговая сессия: {session_start} - {session_end}")
                return session_start, session_end
            else:
                # Если не нашли торговую сессию, используем стандартное время торговой сессии MOEX
                yesterday = current_date - timedelta(days=1)
                # Стандартное время торговой сессии MOEX: 10:00 - 23:50 МСК (основная + вечерняя)
                from_date = datetime.combine(yesterday, datetime.min.time().replace(hour=10, minute=0)).replace(tzinfo=market_hours.moscow_tz)
                to_date = datetime.combine(yesterday, datetime.min.time().replace(hour=23, minute=50)).replace(tzinfo=market_hours.moscow_tz)
                self._logger.warning("Не найдена торговая сессия, используем стандартное время MOEX (10:00-23:50)")
                return from_date, to_date
                
        except Exception as e:
            self._logger.error(f"Ошибка определения периода последней сессии: {e}")
            # Fallback: используем стандартное время торговой сессии MOEX
            yesterday = datetime.now(market_hours.moscow_tz).date() - timedelta(days=1)
            from_date = datetime.combine(yesterday, datetime.min.time().replace(hour=10, minute=0)).replace(tzinfo=market_hours.moscow_tz)
            to_date = datetime.combine(yesterday, datetime.min.time().replace(hour=23, minute=50)).replace(tzinfo=market_hours.moscow_tz)
            self._logger.warning("Fallback: используем стандартное время MOEX (10:00-23:50)")
            return from_date, to_date
