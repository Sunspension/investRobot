import numpy as np

from scipy.signal import find_peaks
from collections import deque
from talipp.indicators import MACD, ATR
from talipp.ohlcv import OHLCV
from robotlib.utils.money import Money
from tinkoff.invest import Candle, HistoricCandle
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum
from robotlib.trading.event_bus_interface import EventType, TradingEvent
from visualization.event_visualizer_interface import VisualizationSinkable
from robotlib.signal_types import Signal, Order
import asyncio


class SignalManager:
    """
    Отвечает за сбор свечей, вычисление индикаторов и генерацию торговых сигналов.
    Вычисляет MACD, ATR и обнаруживает пики/впадины по MACD-гистограмме.
    """

    def __init__(
        self,
        macd_fast=6,
        macd_slow=11,
        macd_signal=9,
        atr_period=7,
        vol_period=14,
        lookback_min=6,
        lookback_max=20,
        peak_prominence=0.2,
        event_bus=None,
        visualization_sink: VisualizationSinkable | None = None,
    ):
        self._candles = deque(maxlen=2000)  # можно расширить, если нужно хранить сырые данные
        
        self._macd = MACD(
            fast_period=macd_fast, 
            slow_period=macd_slow, 
            signal_period=macd_signal
        )
        self._atr = ATR(period=atr_period)
        self._vol_period = vol_period
        self._lookback_min = lookback_min
        self._lookback_max = lookback_max
        self._peak_prominence = peak_prominence

        self._hist_window = deque(maxlen=lookback_max)
        self._event_bus = event_bus
        self._sink = visualization_sink

    @property
    def candles(self) -> deque:
        """Возвращает свечи для чтения"""
        return self._candles
    
    def subscribe_to_events(self):
        """Подписывается на события свечей (для совместимости с тестами)"""
        # Метод оставлен для совместимости, но подписка не нужна
        # так как SignalManager теперь работает напрямую
        pass
    
    async def _handle_candle_event(self, event):
        """Обрабатывает событие получения свечи (для совместимости с тестами)"""
        candle = event.data.get('candle')
        if candle:
            return self.add_candle(candle)
        return None

    def add_candle(self, candle: Candle | HistoricCandle) -> Signal:
        price = Money(candle.close).to_float()
        # Добавляем данные для инкрементального расчета MACD
        self._macd.add(price)
        # Добавляем данные для инкрементального расчета ATR
        ohlcv = OHLCV(
            open=Money(candle.open).to_float(),
            high=Money(candle.high).to_float(),
            low=Money(candle.low).to_float(),
            close=price,
            volume=Money(candle.volume).to_float(),
            time=candle.time.timestamp()
        )
        self._atr.add(ohlcv)

        # Сохраняем свечу всегда
        item = {
            'date': candle.time,
            'open': Money(candle.open).to_float(),
            'high': Money(candle.high).to_float(),
            'low': Money(candle.low).to_float(),
            'close': Money(candle.close).to_float(),
            'macd': None,
            'signal': None,
            'histogram': None
        }

        macd_value = self._macd[-1]
        if macd_value is not None:
            item['macd'] = macd_value.macd
            item['signal'] = macd_value.signal
            item['histogram'] = macd_value.histogram

        self._candles.append(item)

        if macd_value is None:
            return None  # недостаточно данных для MACD

        # Добавляем текущее значение гистограммы в окно
        self._hist_window.append(macd_value.histogram)

        if len(self._hist_window) < self._lookback_min:
            return None  # ждём накопления данных

        # Рассчитать адаптивный lookback по волатильности
        atr_values = self._atr[-self._vol_period:]
        if any(x is None for x in atr_values):
            return None
        
        atr_mean = np.nanmean(atr_values)
        if np.isnan(atr_mean):
            return None  # пропускаем шаг, если нет валидных данных

        vol_norm = self._atr[-1] / (atr_mean + 1e-6)

        # Адаптивный размер окна
        lookback = int(self._lookback_max - (self._lookback_max - self._lookback_min) * min(vol_norm, 1))
        lookback = max(self._lookback_min, min(lookback, self._lookback_max))

        if len(self._hist_window) < lookback:
            return None

        loopback_array = list(self._hist_window)[-lookback:]
        if any([x is None for x in loopback_array]):
            return None
        
        hist_array = np.array(loopback_array)
        troughs, _ = find_peaks(-hist_array, prominence=self._peak_prominence)
        peaks, _ = find_peaks(hist_array, prominence=self._peak_prominence)

        # Проверим ближайшие индексы для сигналов (последние 5 баров)
        check_last_n = 5
        current_idx = lookback - 1
        recent_indices = [current_idx - i for i in range(check_last_n) if current_idx - i >= 0]

        # Сигналы на основе пиков и впадин
        signal = Signal(
            macd=macd_value.macd,
            signal=macd_value.signal,
            histogram=macd_value.histogram,
            macd_prev=self._macd[-2].macd if len(self._macd) > 1 else None,
            signal_prev=self._macd[-2].signal if len(self._macd) > 1 else None,
            peak_detected=any(idx in peaks for idx in recent_indices),
            trough_detected=any(idx in troughs for idx in recent_indices),
            candle=candle
        )
        
        # Публикуем событие генерации сигнала (для визуализации)
        try:
            if self._sink is not None:
                loop = asyncio.get_running_loop()
                loop.create_task(self._sink.on_signal(signal, getattr(candle, 'figi', 'unknown'), price))
            elif self._event_bus:
                signal_event = TradingEvent(
                    EventType.SIGNAL_GENERATED,
                    {
                        'signal': signal,
                        'figi': getattr(candle, 'figi', 'unknown'),
                        'price': price
                    }
                )
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._event_bus.publish(signal_event))
                except RuntimeError:
                    asyncio.run(self._event_bus.publish(signal_event))
        except Exception:
            pass
        
        return signal
