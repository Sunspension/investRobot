"""
GPU-ускоренные технические индикаторы для бэктестинга
Использует PyTorch с MPS (Metal Performance Shaders) для Apple Silicon
"""

import torch
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass
from scipy.signal import find_peaks


@dataclass
class GPUOHLCV:
    """GPU-версия OHLCV данных"""
    open: torch.Tensor
    high: torch.Tensor
    low: torch.Tensor
    close: torch.Tensor
    volume: torch.Tensor
    time: torch.Tensor


class GPUMACD:
    """GPU-версия MACD индикатора"""
    
    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9, device: str = "mps"):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.device = device if torch.backends.mps.is_available() else "cpu"
        
        # Буферы для EMA
        self.fast_ema = None
        self.slow_ema = None
        self.signal_ema = None
        self.macd_line = None
        self.histogram = None
        
    def add(self, price: float) -> Optional[dict]:
        """Добавляет новую цену и возвращает MACD значения"""
        if not hasattr(self, '_prices'):
            self._prices = []
            
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


class GPUATR:
    """GPU-версия ATR индикатора"""
    
    def __init__(self, period: int = 14, device: str = "mps"):
        self.period = period
        self.device = device if torch.backends.mps.is_available() else "cpu"
        
    def add(self, ohlcv: GPUOHLCV) -> Optional[float]:
        """Добавляет новые OHLCV данные и возвращает ATR"""
        if not hasattr(self, '_ohlcv_data'):
            self._ohlcv_data = []
            
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


class GPUPeakDetector:
    """GPU-версия детектора пиков"""
    
    def __init__(self, device: str = "mps"):
        self.device = device if torch.backends.mps.is_available() else "cpu"
        
    def find_peaks(self, data: torch.Tensor, prominence: float = 0.1) -> Tuple[torch.Tensor, dict]:
        """Находит пики в данных используя scipy.signal.find_peaks"""
        # Конвертируем в numpy для использования scipy
        data_np = data.cpu().numpy()
        
        peaks, properties = find_peaks(data_np, prominence=prominence)
        
        return torch.tensor(peaks, device=self.device), properties
    
    def find_troughs(self, data: torch.Tensor, prominence: float = 0.1) -> Tuple[torch.Tensor, dict]:
        """Находит впадины в данных используя scipy.signal.find_peaks"""
        # Инвертируем данные для поиска минимумов
        inverted_data = -data
        
        # Конвертируем в numpy для использования scipy
        data_np = inverted_data.cpu().numpy()
        
        peaks, properties = find_peaks(data_np, prominence=prominence)
        
        return torch.tensor(peaks, device=self.device), properties


class GPUSignalManager:
    """GPU-версия SignalManager для массовых вычислений"""
    
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
        self.macd = GPUMACD(macd_fast, macd_slow, macd_signal, self.device)
        self.atr = GPUATR(atr_period, self.device)
        self.peak_detector = GPUPeakDetector(self.device)
        
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
            
        # Адаптивный lookback на основе волатильности
        atr_values = [c['atr'] for c in self.candles[-14:]]
        if len(atr_values) < 14:
            return None
            
        atr_mean = np.mean(atr_values)
        vol_norm = atr_result / (atr_mean + 1e-6)
        
        # Адаптивный размер окна
        adaptive_lookback = int(self.lookback_min + (self.lookback_max - self.lookback_min) * vol_norm)
        adaptive_lookback = max(self.lookback_min, min(adaptive_lookback, self.lookback_max))
        
        if len(self.histogram_window) < adaptive_lookback:
            return None
            
        # Поиск пиков и впадин
        hist_tensor = torch.tensor(self.histogram_window[-adaptive_lookback:], device=self.device)
        
        peaks, _ = self.peak_detector.find_peaks(hist_tensor, self.peak_prominence)
        troughs, _ = self.peak_detector.find_troughs(hist_tensor, self.peak_prominence)
        
        # Определяем сигналы (проверяем последние 5 баров)
        check_last_n = 5
        current_idx = len(hist_tensor) - 1
        recent_indices = [current_idx - i for i in range(check_last_n) if current_idx - i >= 0]
        
        peak_detected = any(idx in peaks for idx in recent_indices)
        trough_detected = any(idx in troughs for idx in recent_indices)
        
        return {
            'macd': macd_result['macd'],
            'signal': macd_result['signal'],
            'histogram': macd_result['histogram'],
            'peak_detected': peak_detected,
            'trough_detected': trough_detected,
            'candle': candle_data
        }


def batch_process_candles(candles_data: List[dict], 
                         param_combinations: List[dict],
                         device: str = "mps") -> torch.Tensor:
    """
    Обрабатывает множество свечей для множества комбинаций параметров одновременно
    Возвращает тензор с результатами для всех комбинаций
    """
    device = device if torch.backends.mps.is_available() else "cpu"
    
    # Конвертируем данные свечей в тензоры
    n_candles = len(candles_data)
    n_combinations = len(param_combinations)
    
    # Создаем тензоры для всех комбинаций параметров
    results = torch.zeros(n_combinations, device=device)
    
    for i, params in enumerate(param_combinations):
        signal_manager = GPUSignalManager(
            macd_fast=params['macd_fast'],
            macd_slow=params['macd_slow'],
            macd_signal=params['macd_signal'],
            atr_period=params['atr_period'],
            lookback_min=params['lookback_min'],
            lookback_max=params['lookback_max'],
            peak_prominence=params['peak_prominence'],
            device=device
        )
        
        # Обрабатываем свечи
        total_income = 0
        for candle_data in candles_data:
            ohlcv = GPUOHLCV(
                open=torch.tensor(candle_data['open'], device=device),
                high=torch.tensor(candle_data['high'], device=device),
                low=torch.tensor(candle_data['low'], device=device),
                close=torch.tensor(candle_data['close'], device=device),
                volume=torch.tensor(candle_data['volume'], device=device),
                time=torch.tensor(candle_data['time'], device=device)
            )
            
            signal = signal_manager.add_candle(ohlcv)
            if signal and signal['peak_detected']:
                # Простая логика торговли - покупаем на пиках
                total_income += 100  # Упрощенная логика
            elif signal and signal['trough_detected']:
                # Продаем на впадинах
                total_income -= 100
                
        results[i] = total_income
        
    return results
