"""
Быстрая GPU-версия индикаторов без сложного поиска пиков
"""

import torch
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class GPUOHLCV:
    """GPU-версия OHLCV данных"""
    open: torch.Tensor
    high: torch.Tensor
    low: torch.Tensor
    close: torch.Tensor
    volume: torch.Tensor
    time: torch.Tensor


class GPUMACDFast:
    """Быстрая GPU-версия MACD индикатора"""
    
    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9, device: str = "mps"):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.device = device if torch.backends.mps.is_available() else "cpu"
        
        # Буферы для EMA
        self._prices = []
        
    def add(self, price: float) -> Optional[dict]:
        """Добавляет новую цену и возвращает MACD значения"""
        self._prices.append(price)
        
        if len(self._prices) < self.slow_period:
            return None
            
        # Конвертируем в тензор
        prices_tensor = torch.tensor(self._prices, dtype=torch.float32, device=self.device)
        
        # Вычисляем EMA
        fast_ema = self._calculate_ema(prices_tensor, self.fast_period)
        slow_ema = self._calculate_ema(prices_tensor, self.slow_period)
        
        if len(fast_ema) < self.signal_period:
            return None
            
        # MACD линия
        macd_line = fast_ema - slow_ema
        
        # Signal линия (EMA от MACD)
        signal_line = self._calculate_ema(macd_line, self.signal_period)
        
        # Гистограмма
        histogram = macd_line - signal_line
        
        # Возвращаем последние значения
        return {
            'macd': macd_line[-1].item(),
            'signal': signal_line[-1].item(),
            'histogram': histogram[-1].item()
        }
    
    def _calculate_ema(self, data: torch.Tensor, period: int) -> torch.Tensor:
        """Вычисляет экспоненциальное скользящее среднее"""
        if len(data) < period:
            return torch.zeros_like(data)
            
        alpha = 2.0 / (period + 1)
        ema = torch.zeros_like(data)
        ema[0] = data[0]
        
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i-1]
            
        return ema


class GPUATRFast:
    """Быстрая GPU-версия ATR индикатора"""
    
    def __init__(self, period: int = 14, device: str = "mps"):
        self.period = period
        self.device = device if torch.backends.mps.is_available() else "cpu"
        self._ohlcv_data = []
        
    def add(self, ohlcv: GPUOHLCV) -> Optional[float]:
        """Добавляет новые OHLCV данные и возвращает ATR"""
        self._ohlcv_data.append(ohlcv)
        
        if len(self._ohlcv_data) < self.period + 1:
            return None
            
        # Вычисляем True Range
        tr_values = []
        for i in range(1, len(self._ohlcv_data)):
            current = self._ohlcv_data[i]
            previous = self._ohlcv_data[i-1]
            
            tr1 = current.high - current.low
            tr2 = torch.abs(current.high - previous.close)
            tr3 = torch.abs(current.low - previous.close)
            
            tr = torch.max(torch.stack([tr1, tr2, tr3]))
            tr_values.append(tr)
            
        # Конвертируем в тензор
        tr_tensor = torch.stack(tr_values)
        
        # Вычисляем ATR как EMA от TR
        atr = self._calculate_ema(tr_tensor, self.period)
        
        return atr[-1].item()
    
    def _calculate_ema(self, data: torch.Tensor, period: int) -> torch.Tensor:
        """Вычисляет экспоненциальное скользящее среднее"""
        if len(data) < period:
            return torch.zeros_like(data)
            
        alpha = 2.0 / (period + 1)
        ema = torch.zeros_like(data)
        ema[0] = data[0]
        
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i-1]
            
        return ema


class GPUSignalManagerFast:
    """Быстрая GPU-версия SignalManager без сложного поиска пиков"""
    
    def __init__(self, 
                 macd_fast: int = 6,
                 macd_slow: int = 11, 
                 macd_signal: int = 9,
                 atr_period: int = 7,
                 lookback_min: int = 6,
                 lookback_max: int = 20,
                 peak_prominence: float = 0.2,
                 device: str = "mps"):
        
        self.device = device if torch.backends.mps.is_available() else "cpu"
        self.lookback_min = lookback_min
        self.lookback_max = lookback_max
        self.peak_prominence = peak_prominence
        
        # Инициализируем индикаторы
        self.macd = GPUMACDFast(macd_fast, macd_slow, macd_signal, self.device)
        self.atr = GPUATRFast(atr_period, self.device)
        
        # Буферы для данных
        self.candles = []
        self.histogram_window = []
        
    def add_candle(self, ohlcv: GPUOHLCV) -> Optional[dict]:
        """Добавляет свечу и возвращает сигнал"""
        # Добавляем данные в индикаторы
        macd_result = self.macd.add(ohlcv.close.item())
        atr_result = self.atr.add(ohlcv)
        
        if macd_result is None or atr_result is None:
            return None
            
        # Сохраняем данные свечи
        candle_data = {
            'time': ohlcv.time.item(),
            'open': ohlcv.open.item(),
            'high': ohlcv.high.item(),
            'low': ohlcv.low.item(),
            'close': ohlcv.close.item(),
            'macd': macd_result['macd'],
            'signal': macd_result['signal'],
            'histogram': macd_result['histogram'],
            'atr': atr_result
        }
        
        self.candles.append(candle_data)
        self.histogram_window.append(macd_result['histogram'])
        
        # Ограничиваем размер буфера
        if len(self.histogram_window) > self.lookback_max:
            self.histogram_window.pop(0)
            
        if len(self.histogram_window) < self.lookback_min:
            return None
            
        # Простой поиск пиков без сложных вычислений
        peak_detected = False
        trough_detected = False
        
        if len(self.histogram_window) >= 3:
            current = self.histogram_window[-1]
            prev = self.histogram_window[-2]
            prev2 = self.histogram_window[-3]
            
            # Простая логика: пик если текущее значение больше предыдущих
            if current > prev and prev > prev2:
                peak_detected = True
            # Впадина если текущее значение меньше предыдущих
            elif current < prev and prev < prev2:
                trough_detected = True
        
        return {
            'macd': macd_result['macd'],
            'signal': macd_result['signal'],
            'histogram': macd_result['histogram'],
            'peak_detected': peak_detected,
            'trough_detected': trough_detected,
            'candle': candle_data
        }
