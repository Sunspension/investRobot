"""
Модуль для работы со стримом рыночных данных
"""
import asyncio
from typing import Callable, Optional, List
from collections import deque

from tinkoff.invest import Candle, SubscriptionInterval
from tinkoff.invest.market_data_stream.async_market_data_stream_manager import AsyncMarketDataStreamManager

from robotlib.signal_manager import SignalManager
from robotlib.utils.logger import get_logger
from robotlib.utils.market_hours_enhanced import get_market_status_enhanced
from robotlib.trading.event_bus_interface import EventBusable, EventType, TradingEvent


class MarketDataStream:
    """Класс для управления стримом рыночных данных"""
    
    def __init__(
        self, 
        api_client, 
        signal_manager: SignalManager, 
        figi: str = "FUTIMOEXF000",
        cache_size: int = 100,
        visualizer=None,
        event_bus: Optional[EventBusable] = None
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
        self._signal_manager = signal_manager
        self._figi = figi
        self._visualizer = visualizer
        self._event_bus = event_bus
        
        self._stream_manager: Optional[AsyncMarketDataStreamManager] = None
        self._is_running = False
        self.logger = get_logger(__name__)
        
        # Кэширование данных
        self._cached_candles: deque = deque(maxlen=cache_size)
        self._current_price: Optional[float] = None
        
        # Колбэки для обработки данных
        self._candle_callbacks: List[Callable[[Candle], None]] = []
        self._signal_callbacks: List[Callable] = []
    
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
    
    async def start(self) -> bool:
        """
        Запускает стрим рыночных данных
        
        Returns:
            True если стрим запущен успешно, False иначе
        """
        try:
            self.logger.info(f"Запуск стрима рыночных данных для {self._figi}")
            
            # Создаем стрим менеджер
            self._stream_manager = await self._api_client.create_market_data_stream()
            
            if not self._stream_manager:
                self.logger.error("Не удалось создать стрим менеджер")
                return False
            
            # Проверяем статус рынка
            from robotlib.utils.tinkoff_market_hours import get_tinkoff_market_hours
            market_hours = await get_tinkoff_market_hours()
            market_status = await market_hours.get_trading_status()
            
            if market_status.get('is_trading', False):
                # Рынок открыт - подписываемся на реальные данные
                await self._stream_manager.subscribe_candles([self._figi], SubscriptionInterval.SUBSCRIPTION_INTERVAL_ONE_MINUTE)
                self.logger.info("Рынок открыт, подписка на реальные данные активирована")
                
                # Запускаем обработку данных
                self._is_running = True
                asyncio.create_task(self._process_stream())
            else:
                # Рынок закрыт - загружаем исторические данные последней сессии
                self.logger.info("Рынок закрыт, загружаем исторические данные последней сессии")
                self._is_running = True
                asyncio.create_task(self._load_historical_data())
            
            self.logger.info("Стрим рыночных данных запущен")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка запуска стрима: {e}")
            return False
    
    async def stop(self) -> None:
        """Останавливает стрим рыночных данных"""
        try:
            self.logger.info("Остановка стрима рыночных данных")
            
            self._is_running = False
            
            if self._stream_manager:
                try:
                    await self._stream_manager.stop()
                except Exception as e:
                    self.logger.warning(f"Ошибка остановки стрим менеджера: {e}")
                finally:
                    self._stream_manager = None
            
            self.logger.info("Стрим рыночных данных остановлен")
            
        except Exception as e:
            self.logger.error(f"Ошибка остановки стрима: {e}")
    
    async def _process_stream(self) -> None:
        """Обрабатывает данные из стрима"""
        try:
            while self._is_running and self._stream_manager:
                try:
                    # Получаем данные из стрима
                    async for market_data in self._stream_manager:
                        if not self._is_running:
                            break
                        
                        # Обрабатываем свечи
                        if hasattr(market_data, 'candle') and market_data.candle:
                            await self._process_candle(market_data.candle)
                        
                        # Обрабатываем другие типы данных
                        if hasattr(market_data, 'trade') and market_data.trade:
                            await self._process_trade(market_data.trade)
                        
                        if hasattr(market_data, 'orderbook') and market_data.orderbook:
                            await self._process_orderbook(market_data.orderbook)
                            
                except Exception as stream_error:
                    # Обрабатываем ошибки стрима отдельно
                    if "CANCELLED" in str(stream_error) or "RST_STREAM" in str(stream_error):
                        self.logger.warning(f"Стрим отменен сервером: {stream_error}")
                        self._is_running = False
                        break
                    else:
                        self.logger.error(f"Ошибка в стриме: {stream_error}")
                        # Пытаемся переподключиться
                        await asyncio.sleep(5)
                        break
                        
        except Exception as e:
            self.logger.error(f"Ошибка обработки стрима: {e}")
            self._is_running = False
    
    def _process_candle(self, candle: Candle) -> None:
        """
        Обрабатывает полученную свечу
        
        Args:
            candle: Свеча от API
        """
        try:
            if not candle:
                self.logger.warning("Получена пустая свеча")
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
            self.logger.debug(f"Получена свеча: {candle.time} - {self._current_price} (FIGI: {figi_info})")
            
            # Обрабатываем свечу в SignalManager
            if self._signal_manager:
                signal = self._signal_manager.add_candle(candle)
            
            # Публикуем событие свечи
            if self._event_bus:
                event = TradingEvent(
                    EventType.CANDLE_RECEIVED,
                    {
                        'candle': candle,
                        'price': self._current_price,
                        'figi': self._figi
                    }
                )
                asyncio.create_task(self._event_bus.publish(event))
                
                # Если получен сигнал, вызываем колбэки для сигналов
                if signal:
                    # Публикуем событие сигнала
                    signal_event = TradingEvent(
                        EventType.SIGNAL_GENERATED,
                        {
                            'signal': signal,
                            'figi': self._figi,
                            'price': self._current_price
                        }
                    )
                    asyncio.create_task(self._event_bus.publish(signal_event))
                    
                    for callback in self._signal_callbacks:
                        try:
                            callback(signal)
                        except Exception as e:
                            self.logger.error(f"Ошибка в колбэке сигнала: {e}")
            
            # Вызываем колбэки для свечей
            for callback in self._candle_callbacks:
                try:
                    callback(candle)
                except Exception as e:
                    self.logger.error(f"Ошибка в колбэке свечи: {e}")
                        
        except Exception as e:
            self.logger.error(f"Ошибка обработки свечи: {e}")
    
    async def _process_trade(self, trade) -> None:
        """Обрабатывает сделку"""
        # Пока что просто логируем
        self.logger.debug(f"Получена сделка: {trade}")
    
    async def _process_orderbook(self, orderbook) -> None:
        """Обрабатывает стакан заявок"""
        # Пока что просто логируем
        self.logger.debug(f"Получен стакан: {orderbook}")
    
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
                self.logger.warning("Кэш свечей пуст")
                return []
            
            # Возвращаем последние count свечей
            return list(self._cached_candles)[-count:]
            
        except Exception as e:
            self.logger.error(f"Ошибка получения последних свечей: {e}")
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
            from datetime import datetime, timedelta
            
            self.logger.info("Загрузка исторических данных последней торговой сессии...")
            
            # Получаем информацию о торговых часах (расширенная версия с поддержкой выходных)
            market_status = await get_market_status_enhanced()
            
            # Определяем период для загрузки
            if market_status.get('is_trading', False):
                session_type = market_status.get('session_type', 'unknown')
                if session_type == 'weekend':
                    # Выходные торги - загружаем данные за последние 4 часа
                    to_date = datetime.now()
                    from_date = to_date - timedelta(hours=4)
                    self.logger.info("Выходные торги, загружаем данные за последние 4 часа")
                elif session_type == 'evening':
                    # Вечерние торги - загружаем данные за последние 2 часа
                    to_date = datetime.now()
                    from_date = to_date - timedelta(hours=2)
                    self.logger.info("Вечерние торги, загружаем данные за последние 2 часа")
                else:
                    # Основные торги - загружаем данные за последние 2 часа
                    to_date = datetime.now()
                    from_date = to_date - timedelta(hours=2)
                    self.logger.info("Основные торги, загружаем данные за последние 2 часа")
            else:
                # Если рынок закрыт, загружаем данные последней торговой сессии
                from_date, to_date = await self._get_last_trading_session_period()
                self.logger.info(f"Рынок закрыт, загружаем данные последней сессии: {from_date} - {to_date}")
            
            # Получаем исторические свечи
            candles_response = await self._api_client.get_candles(
                figi=self._figi,
                from_date=from_date,
                to_date=to_date,
                interval=1  # 1 минута
            )
            
            if candles_response and hasattr(candles_response, 'candles'):
                self.logger.info(f"Загружено {len(candles_response.candles)} исторических свечей")
                
                # Логируем период данных для отладки
                if candles_response.candles:
                    first_candle = candles_response.candles[0]
                    last_candle = candles_response.candles[-1]
                    self.logger.info(f"Период данных: {first_candle.time} - {last_candle.time}")
                
                # Обрабатываем каждую свечу
                for candle in candles_response.candles:
                    self._process_candle(candle)
                    
                    # Отправляем свечу в визуализатор
                    if self._visualizer and hasattr(self._visualizer, 'add_candle'):
                        try:
                            candle_data = {
                                'time': candle.time,
                                'open': candle.open.units + candle.open.nano / 1_000_000_000,
                                'high': candle.high.units + candle.high.nano / 1_000_000_000,
                                'low': candle.low.units + candle.low.nano / 1_000_000_000,
                                'close': candle.close.units + candle.close.nano / 1_000_000_000,
                                'volume': candle.volume
                            }
                            await self._visualizer.add_candle(candle_data)
                        except Exception as e:
                            self.logger.warning(f"Ошибка отправки свечи в визуализатор: {e}")
                
                # После загрузки всех исторических данных уведомляем визуализатор
                if self._visualizer and hasattr(self._visualizer, 'force_update'):
                    try:
                        await self._visualizer.force_update()
                        self.logger.info("✅ Уведомлен визуализатор об обновлении исторических данных")
                    except Exception as e:
                        self.logger.warning(f"Ошибка уведомления визуализатора: {e}")
                    
                    await asyncio.sleep(0.1)  # Небольшая задержка для демонстрации
                
                # Принудительно обновляем интерфейс после загрузки всех данных
                if self._visualizer and hasattr(self._visualizer, 'force_update'):
                    await self._visualizer.force_update()
                    
            else:
                self.logger.warning("Не удалось загрузить исторические данные")
                
        except Exception as e:
            self.logger.error(f"Ошибка загрузки исторических данных: {e}")
    
    async def _get_last_trading_session_period(self) -> tuple:
        """
        Определяет период последней торговой сессии
        
        Returns:
            tuple: (from_date, to_date) - период последней торговой сессии
        """
        try:
            from datetime import datetime, timedelta
            from robotlib.utils.tinkoff_market_hours import get_tinkoff_market_hours
            
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
                if hasattr(main_session['start'], 'tzinfo') and main_session['start'].tzinfo:
                    session_start = main_session['start'].astimezone(market_hours.moscow_tz)
                    session_end = main_session['end'].astimezone(market_hours.moscow_tz)
                else:
                    from datetime import timezone
                    session_start = main_session['start'].replace(tzinfo=timezone.utc).astimezone(market_hours.moscow_tz)
                    session_end = main_session['end'].replace(tzinfo=timezone.utc).astimezone(market_hours.moscow_tz)
                
                self.logger.info(f"Найдена последняя торговая сессия: {session_start} - {session_end}")
                return session_start, session_end
            else:
                # Если не нашли торговую сессию, используем стандартное время торговой сессии MOEX
                yesterday = current_date - timedelta(days=1)
                # Стандартное время торговой сессии MOEX: 10:00 - 23:50 МСК (основная + вечерняя)
                from_date = datetime.combine(yesterday, datetime.min.time().replace(hour=10, minute=0)).replace(tzinfo=market_hours.moscow_tz)
                to_date = datetime.combine(yesterday, datetime.min.time().replace(hour=23, minute=50)).replace(tzinfo=market_hours.moscow_tz)
                self.logger.warning("Не найдена торговая сессия, используем стандартное время MOEX (10:00-23:50)")
                return from_date, to_date
                
        except Exception as e:
            self.logger.error(f"Ошибка определения периода последней сессии: {e}")
            # Fallback: используем стандартное время торговой сессии MOEX
            from datetime import datetime, timedelta
            yesterday = datetime.now(market_hours.moscow_tz).date() - timedelta(days=1)
            from_date = datetime.combine(yesterday, datetime.min.time().replace(hour=10, minute=0)).replace(tzinfo=market_hours.moscow_tz)
            to_date = datetime.combine(yesterday, datetime.min.time().replace(hour=23, minute=50)).replace(tzinfo=market_hours.moscow_tz)
            self.logger.warning("Fallback: используем стандартное время MOEX (10:00-23:50)")
            return from_date, to_date
