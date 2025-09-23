import numpy as np

from collections import deque
from robotlib.indicators import IncrementalMACD, IncrementalATR, MACDPoint
from robotlib.utils.peaks import find_peaks_indices, find_troughs_indices
from robotlib.utils.money import Money
from tinkoff.invest import Candle, HistoricCandle
from robotlib.visualization_interfaces import TradingEventSinkable
from robotlib.utils.logger import get_logger
from robotlib.signal_types import Signal
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
        visualization_sink: TradingEventSinkable | None = None,
    ):
        self._candles = deque(maxlen=2000)  # можно расширить, если нужно хранить сырые данные
        self._logger = get_logger(__name__)
        
        self._macd = IncrementalMACD(
            fast_period=macd_fast,
            slow_period=macd_slow,
            signal_period=macd_signal,
        )
        self._atr = IncrementalATR(period=atr_period)
        self._vol_period = vol_period
        self._lookback_min = lookback_min
        self._lookback_max = lookback_max
        self._peak_prominence = peak_prominence

        self._hist_window = deque(maxlen=lookback_max)
        self._atr_window = deque(maxlen=vol_period)
        self._macd_history: deque[MACDPoint] = deque(maxlen=3)
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

    def add_candle(self, candle: Candle | HistoricCandle) -> Signal | None:
        price = Money(candle.close).to_float()
        # Инкрементальные обновления индикаторов
        macd_value = self._macd.update(price)
        atr_value = self._atr.update(
            high=Money(candle.high).to_float(),
            low=Money(candle.low).to_float(),
            close=price,
        )
        if atr_value is not None:
            self._atr_window.append(atr_value)

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

        if macd_value is not None:
            item['macd'] = macd_value.macd
            item['signal'] = macd_value.signal
            item['histogram'] = macd_value.histogram
            self._macd_history.append(macd_value)

        self._candles.append(item)

        if macd_value is None:
            return None  # недостаточно данных для MACD

        # Добавляем текущее значение гистограммы в окно
        self._hist_window.append(macd_value.histogram)

        if len(self._hist_window) < self._lookback_min:
            return None  # ждём накопления данных

        # Рассчитать адаптивный lookback по волатильности
        if len(self._atr_window) < self._vol_period:
            return None
        atr_values = list(self._atr_window)
        atr_mean = float(np.nanmean(atr_values))
        if np.isnan(atr_mean):
            return None  # пропускаем шаг, если нет валидных данных

        current_atr = self._atr.current()
        if current_atr is None:
            return None
        vol_norm = current_atr / (atr_mean + 1e-6)

        # Адаптивный размер окна
        lookback = int(self._lookback_max - (self._lookback_max - self._lookback_min) * min(vol_norm, 1))
        lookback = max(self._lookback_min, min(lookback, self._lookback_max))

        if len(self._hist_window) < lookback:
            return None

        loopback_array = list(self._hist_window)[-lookback:]
        if any([x is None for x in loopback_array]):
            return None
        
        hist_array = np.array(loopback_array)
        troughs = find_troughs_indices(hist_array.tolist(), prominence=self._peak_prominence)
        peaks = find_peaks_indices(hist_array.tolist(), prominence=self._peak_prominence)

        # Проверим ближайшие индексы для сигналов (последние 5 баров)
        check_last_n = 5
        current_idx = lookback - 1
        recent_indices = [current_idx - i for i in range(check_last_n) if current_idx - i >= 0]

        # Сигналы на основе пиков и впадин
        macd_prev = self._macd_history[-2] if len(self._macd_history) > 1 else None

        signal = Signal(
            macd=macd_value.macd,
            signal=macd_value.signal,
            histogram=macd_value.histogram,
            macd_prev=macd_prev.macd if macd_prev else None,
            signal_prev=macd_prev.signal if macd_prev else None,
            peak_detected=any(idx in peaks for idx in recent_indices),
            trough_detected=any(idx in troughs for idx in recent_indices),
            candle=candle
        )
        # Логируем факт генерации сигнала (уровень INFO для видимости в проде)
        try:
            self._logger.info(
                f"Signal emitted: hist={signal.histogram:.4f}, peak={signal.peak_detected}, "
                f"trough={signal.trough_detected}, time={getattr(candle, 'time', None)}"
            )
        except Exception:
            # Никогда не ломаем поток из-за логирования
            pass

        # Возвращаем сигнал наверх (доставка во внешний sink выполняется на application-уровне)
        return signal

    def add_bar_values(
        self,
        *,
        time,
        open_price: float,
        high_price: float,
        low_price: float,
        close_price: float,
    ) -> Signal:
        """Добавляет бар значениями (для прогрева из БД) без генерации ордеров.

        Возвращает рассчитанный Signal или None, аналогично add_candle, но принимает числа.
        """
        price = float(close_price)
        macd_value = self._macd.update(price)
        atr_value = self._atr.update(
            high=float(high_price),
            low=float(low_price),
            close=price,
        )
        if atr_value is not None:
            self._atr_window.append(atr_value)

        item = {
            'date': time,
            'open': float(open_price),
            'high': float(high_price),
            'low': float(low_price),
            'close': float(close_price),
            'macd': None,
            'signal': None,
            'histogram': None
        }

        if macd_value is not None:
            item['macd'] = macd_value.macd
            item['signal'] = macd_value.signal
            item['histogram'] = macd_value.histogram
            self._macd_history.append(macd_value)

        self._candles.append(item)

        if macd_value is None:
            return None

        self._hist_window.append(macd_value.histogram)

        if len(self._hist_window) < self._lookback_min:
            return None

        if len(self._atr_window) < self._vol_period:
            return None
        atr_values = list(self._atr_window)
        atr_mean = float(np.nanmean(atr_values))
        if np.isnan(atr_mean):
            return None

        current_atr = self._atr.current()
        if current_atr is None:
            return None
        vol_norm = current_atr / (atr_mean + 1e-6)

        lookback = int(self._lookback_max - (self._lookback_max - self._lookback_min) * min(vol_norm, 1))
        lookback = max(self._lookback_min, min(lookback, self._lookback_max))

        if len(self._hist_window) < lookback:
            return None

        loopback_array = list(self._hist_window)[-lookback:]
        if any([x is None for x in loopback_array]):
            return None

        hist_array = np.array(loopback_array)
        troughs = find_troughs_indices(hist_array.tolist(), prominence=self._peak_prominence)
        peaks = find_peaks_indices(hist_array.tolist(), prominence=self._peak_prominence)

        check_last_n = 5
        current_idx = lookback - 1
        recent_indices = [current_idx - i for i in range(check_last_n) if current_idx - i >= 0]

        macd_prev = self._macd_history[-2] if len(self._macd_history) > 1 else None

        signal = Signal(
            macd=macd_value.macd,
            signal=macd_value.signal,
            histogram=macd_value.histogram,
            macd_prev=macd_prev.macd if macd_prev else None,
            signal_prev=macd_prev.signal if macd_prev else None,
            peak_detected=any(idx in peaks for idx in recent_indices),
            trough_detected=any(idx in troughs for idx in recent_indices),
            candle=None,
        )
        return signal
