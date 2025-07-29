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


class OrderDirection(Enum):
    """Направление ордера"""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """Тип ордера"""
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(Enum):
    """Статус исполнения ордера"""
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    PENDING = "pending"


@dataclass
class Signal:
    macd: float = None
    signal: float = None
    histogram: float = None
    macd_prev: float = None
    signal_prev: float = None
    peak_detected: bool = False
    trough_detected: bool = False
    candle: Candle | HistoricCandle = None

@dataclass
class OrderIntent:
    """Намерение на совершение сделки (что хотим сделать)"""
    direction: OrderDirection
    quantity: int
    order_type: OrderType
    limit_price: Optional[float] = None  # только для limit ордеров
    figi: Optional[str] = None  # инструмент
    created_at: datetime = field(default_factory=datetime.now)

    def __str__(self):
        if self.order_type == OrderType.MARKET:
            return f"{self.direction.value.upper()} {self.quantity} @ MARKET"
        else:
            return f"{self.direction.value.upper()} {self.quantity} @ {self.limit_price}"


@dataclass
class OrderExecution:
    """Результат исполнения ордера (что получилось)"""
    order_id: str
    intent: OrderIntent
    executed_price: float
    executed_quantity: int
    executed_at: datetime
    status: OrderStatus
    commission: float = 0.0
    profit: Optional[float] = None  # для закрытия позиций

    def __str__(self):
        return f"{self.intent.direction.value.upper()} {self.executed_quantity} @ {self.executed_price} [{self.status.value}]"


@dataclass
class Order:
    """Старый класс Order - оставляем для обратной совместимости"""
    type: str = None
    price: float = None
    marker_price: float = None
    quantity: int = None
    date: datetime = None
    profit: int = None
    commission: float = None  # Комиссия за сделку

    def __str__(self):
        if self.profit is None:
            commission_str = f" commission: {self.commission:.2f}" if self.commission is not None else ""
            return f"{self.date.strftime('%Y-%m-%d %H:%M')}: {self.type} at price: {self.price} quantity: {self.quantity}{commission_str}" 
        else:
            commission_str = f" commission: {self.commission:.2f}" if self.commission is not None else ""
            return f"{self.date.strftime('%Y-%m-%d %H:%M')}: {self.type} at price: {self.price} quantity: {self.quantity} profit: {self.profit}{commission_str}"


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
    ):
        self.candles = deque(maxlen=2000)  # можно расширить, если нужно хранить сырые данные
        
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

        macd_value = self._macd[-1]
        if macd_value is None:
            return None  # недостаточно данных

        item = {
                'date': candle.time,
                'open': Money(candle.open).to_float(),
                'high': Money(candle.high).to_float(),
                'low': Money(candle.low).to_float(),
                'close': Money(candle.close).to_float(),
                'macd': macd_value.macd,
                'signal': macd_value.signal,
                'histogram': macd_value.histogram
        }

        self.candles.append(item)

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
            return None # пропускаем шаг, если нет валидных данных

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
        return Signal(
            macd=macd_value.macd,
            signal=macd_value.signal,
            histogram=macd_value.histogram,
            macd_prev=self._macd[-2].macd if len(self._macd) > 1 else None,
            signal_prev=self._macd[-2].signal if len(self._macd) > 1 else None,
            peak_detected=any(idx in peaks for idx in recent_indices),
            trough_detected=any(idx in troughs for idx in recent_indices),
            candle=candle
        )