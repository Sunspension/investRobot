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


class MarketDataStream:
    """Класс для управления стримом рыночных данных"""
    
    def __init__(
        self, 
        api_client, 
        signal_manager: SignalManager, 
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
        self.api_client = api_client
        self.signal_manager = signal_manager
        self.figi = figi
        
        self.stream_manager: Optional[AsyncMarketDataStreamManager] = None
        self.is_running = False
        self.logger = get_logger(__name__)
        
        # Кэширование данных
        self.cached_candles: deque = deque(maxlen=cache_size)
        self.current_price: Optional[float] = None
        
        # Колбэки для обработки данных
        self.candle_callbacks: List[Callable[[Candle], None]] = []
        self.signal_callbacks: List[Callable] = []
    
    async def start(self) -> bool:
        """
        Запускает стрим рыночных данных
        
        Returns:
            True если стрим запущен успешно, False иначе
        """
        try:
            self.logger.info(f"Запуск стрима рыночных данных для {self.figi}")
            
            # Создаем стрим менеджер
            self.stream_manager = await self.api_client.create_market_data_stream()
            
            if not self.stream_manager:
                self.logger.error("Не удалось создать стрим менеджер")
                return False
            
            # Подписываемся на свечи
            await self.stream_manager.subscribe_candles([self.figi], SubscriptionInterval.SUBSCRIPTION_INTERVAL_ONE_MINUTE)
            
            # Запускаем обработку данных
            self.is_running = True
            asyncio.create_task(self._process_stream())
            
            self.logger.info("Стрим рыночных данных запущен")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка запуска стрима: {e}")
            return False
    
    async def stop(self) -> None:
        """Останавливает стрим рыночных данных"""
        try:
            self.logger.info("Остановка стрима рыночных данных")
            
            self.is_running = False
            
            if self.stream_manager:
                await self.stream_manager.stop()
                self.stream_manager = None
            
            self.logger.info("Стрим рыночных данных остановлен")
            
        except Exception as e:
            self.logger.error(f"Ошибка остановки стрима: {e}")
    
    async def _process_stream(self) -> None:
        """Обрабатывает данные из стрима"""
        try:
            while self.is_running and self.stream_manager:
                # Получаем данные из стрима
                async for market_data in self.stream_manager:
                    if not self.is_running:
                        break
                    
                    # Обрабатываем свечи
                    if hasattr(market_data, 'candle') and market_data.candle:
                        await self._process_candle(market_data.candle)
                    
                    # Обрабатываем другие типы данных
                    if hasattr(market_data, 'trade') and market_data.trade:
                        await self._process_trade(market_data.trade)
                    
                    if hasattr(market_data, 'orderbook') and market_data.orderbook:
                        await self._process_orderbook(market_data.orderbook)
                        
        except Exception as e:
            self.logger.error(f"Ошибка обработки стрима: {e}")
            self.is_running = False
    
    def _process_candle(self, candle: Candle) -> None:
        """
        Обрабатывает полученную свечу
        
        Args:
            candle: Свеча от API
        """
        try:
            # Проверяем, что свеча для нашего инструмента
            if candle.figi != self.figi:
                return
            
            # Обновляем кэш и текущую цену
            self.cached_candles.append(candle)
            self.current_price = candle.close.units + candle.close.nano / 1_000_000_000
            
            # Логируем получение свечи
            self.logger.debug(f"Получена свеча: {candle.time} - {self.current_price}")
            
            # Обрабатываем свечу в SignalManager
            signal = self.signal_manager.add_candle(candle)
            
            # Вызываем колбэки для свечей
            for callback in self.candle_callbacks:
                try:
                    callback(candle)
                except Exception as e:
                    self.logger.error(f"Ошибка в колбэке свечи: {e}")
            
            # Если получен сигнал, вызываем колбэки для сигналов
            if signal:
                for callback in self.signal_callbacks:
                    try:
                        callback(signal)
                    except Exception as e:
                        self.logger.error(f"Ошибка в колбэке сигнала: {e}")
                        
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
        self.candle_callbacks.append(callback)
    
    def add_signal_callback(self, callback: Callable) -> None:
        """
        Добавляет колбэк для обработки сигналов
        
        Args:
            callback: Функция для обработки сигналов
        """
        self.signal_callbacks.append(callback)
    
    def remove_candle_callback(self, callback: Callable[[Candle], None]) -> None:
        """Удаляет колбэк для свечей"""
        if callback in self.candle_callbacks:
            self.candle_callbacks.remove(callback)
    
    def remove_signal_callback(self, callback: Callable) -> None:
        """Удаляет колбэк для сигналов"""
        if callback in self.signal_callbacks:
            self.signal_callbacks.remove(callback)
    
    async def get_latest_candles(self, count: int = 10) -> List[Candle]:
        """
        Возвращает последние N свечей из кэша
        
        Args:
            count: Количество свечей для возврата
            
        Returns:
            Список последних свечей
        """
        try:
            if not self.cached_candles:
                self.logger.warning("Кэш свечей пуст")
                return []
            
            # Возвращаем последние count свечей
            return list(self.cached_candles)[-count:]
            
        except Exception as e:
            self.logger.error(f"Ошибка получения последних свечей: {e}")
            return []
    
    async def get_current_price(self) -> Optional[float]:
        """
        Возвращает текущую цену
        
        Returns:
            Текущая цена или None если данных нет
        """
        return self.current_price
    
    def get_cached_candles(self) -> List[Candle]:
        """
        Возвращает все кэшированные свечи
        
        Returns:
            Список всех кэшированных свечей
        """
        return list(self.cached_candles)
    
    def get_cache_size(self) -> int:
        """
        Возвращает размер кэша
        
        Returns:
            Количество свечей в кэше
        """
        return len(self.cached_candles)
    
    def clear_cache(self) -> None:
        """Очищает кэш свечей"""
        self.cached_candles.clear()
        self.current_price = None
        self.logger.info("Кэш свечей очищен")
