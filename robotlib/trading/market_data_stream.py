"""
Модуль для работы со стримом рыночных данных
"""
import asyncio
from datetime import datetime, timedelta, timezone, time
from typing import Callable, Optional, List
from collections import deque
import pytz

from tinkoff.invest import Candle, SubscriptionInterval, MarketDataResponse, GetCandlesResponse, CandleInterval
from tinkoff.invest.market_data_stream.async_market_data_stream_manager import AsyncMarketDataStreamManager

from robotlib.utils.logger import get_logger
from robotlib.utils.market_hours_enhanced import get_market_status_enhanced
from robotlib.utils.tinkoff_market_hours import get_tinkoff_market_hours
from robotlib.trading.interfaces import TinkoffAPIClientable, MarketDataStreamable
from visualization.event_visualizer_interface import VisualizationSinkable


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
        cache_size: int = 100
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
        self._sink: Optional[VisualizationSinkable] = None

    def set_visualization_sink(self, sink: VisualizationSinkable) -> None:
        """Устанавливает приемник визуализации (для прямых вызовов без EventBus)."""
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
        return (self._api_client is not None and 
                self._api_client.services is not None)
    
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
            
            if market_status.get('is_trading', False):
                # Прогрев сигналов и визуализатора историческими данными перед подпиской
                try:
                    self._logger.info("Прогрев историческими данными перед подпиской на реальный стрим")
                    await self._load_historical_data()
                except Exception as warmup_err:
                    self._logger.warning(f"Не удалось выполнить прогрев историческими данными: {warmup_err}")
                
                # Рынок открыт - подписываемся на реальные данные
                # Используем адаптер для убирания путаницы с названиями
                try:
                    from tinkoff.invest import MarketDataRequest, SubscribeCandlesRequest, CandleInstrument, SubscriptionAction
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
                    # subscribe() синхронный
                    self._stream_adapter.subscribe(request)
                    self._logger.info("Подписка на реальные данные через MarketDataRequest успешна")
                except Exception as e:
                    self._logger.error(f"Ошибка подписки на реальные данные: {e}")
                    # Если не удалось подписаться, загружаем исторические данные
                    self._logger.info("Переключаемся на загрузку исторических данных")
                    self._is_running = True
                    asyncio.create_task(self._load_historical_data())
                    return True
                self._logger.info("Рынок открыт, подписка на реальные данные активирована")
                
                # Запускаем обработку данных
                self._is_running = True
                asyncio.create_task(self._process_stream())
            else:
                # Рынок закрыт - загружаем исторические данные последней сессии
                self._logger.info("Рынок закрыт, загружаем исторические данные последней сессии")
                self._is_running = True
                asyncio.create_task(self._load_historical_data())
            
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
                    # Обрабатываем ошибки стрима отдельно
                    if "CANCELLED" in str(stream_error) or "RST_STREAM" in str(stream_error):
                        self._logger.warning(f"Стрим отменен сервером: {stream_error}")
                        self._is_running = False
                        break
                    else:
                        self._logger.error(f"Ошибка в стриме: {stream_error}")
                        # Пытаемся переподключиться
                        await asyncio.sleep(5)
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
            if not candle:
                self._logger.warning("Получена пустая свеча")
                return
                
            # Проверяем, что свеча для нашего инструмента
            candle_figi = getattr(candle, 'figi', self._figi)
            if candle_figi != self._figi:
                return
            
            # Обновляем кэш и текущую цену
            self._cached_candles.append(candle)
            self._current_price = candle.close.units + candle.close.nano / 1_000_000_000
            
            # Логируем получение свечи
            figi_info = getattr(candle, 'figi', self._figi)
            self._logger.debug(f"Получена свеча: {candle.time} - {self._current_price} (FIGI: {figi_info})")
            
            # Публикуем свечу (напрямую в визуализатор либо через EventBus)
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
        """Загружает исторические данные последней торговой сессии"""
        try:
            self._logger.info("Загрузка исторических данных последней торговой сессии...")
            
            # Получаем информацию о торговых часах (расширенная версия с поддержкой выходных)
            market_status = await get_market_status_enhanced()
            
            # Определяем период для загрузки
            if market_status.get('is_trading', False):
                session_type = market_status.get('session_type', 'unknown')
                
                if session_type == 'weekend':
                    # Выходные торги - загружаем данные за последние 4 часа
                    to_date = datetime.now()
                    from_date = to_date - timedelta(hours=4)
                    self._logger.info("Выходные торги, загружаем данные за последние 4 часа")
                elif session_type == 'evening':
                    # Вечерние торги - загружаем данные за последние 2 часа
                    to_date = datetime.now()
                    from_date = to_date - timedelta(hours=2)
                    self._logger.info("Вечерние торги, загружаем данные за последние 2 часа")
                else:
                    # Основные торги - загружаем данные за последние 2 часа
                    to_date = datetime.now()
                    from_date = to_date - timedelta(hours=2)
                    self._logger.info("Основные торги, загружаем данные за последние 2 часа")
            else:
                # Если рынок закрыт, загружаем данные последней торговой сессии
                from_date, to_date = await self._get_last_trading_session_period()
                self._logger.info(f"Рынок закрыт, загружаем данные последней сессии: {from_date} - {to_date}")
            
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
