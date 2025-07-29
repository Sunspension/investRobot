"""
Мок для менеджера сигналов
"""
from typing import List, Dict, Any, Optional
from robotlib.signal_manager import Signal

class MockSignalManager:
    """Мок для менеджера сигналов"""
    
    def __init__(self, **kwargs):
        self._candles = []
        self._signals_enabled = kwargs.get('signals_enabled', True)
        self._signal_frequency = kwargs.get('signal_frequency', 0.3)  # 30% вероятность сигнала
    
    def add_candle(self, candle) -> Optional[Signal]:
        """Мок добавления свечи"""
        # Сохраняем свечу
        candle_data = {
            'date': candle.time,
            'open': getattr(candle, 'open', 100.0),
            'high': getattr(candle, 'high', 105.0),
            'low': getattr(candle, 'low', 95.0),
            'close': getattr(candle, 'close', 100.0),
            'macd': 0.1,
            'signal': 0.05,
            'histogram': 0.05
        }
        self._candles.append(candle_data)
        
        # Иногда возвращаем сигнал
        if self._signals_enabled and len(self._candles) % 3 == 0:
            return Signal(
                trough_detected=True,
                peak_detected=False,
                histogram=0.1,
                macd=0.15,
                signal=0.1,
                macd_prev=0.05,
                signal_prev=0.08,
                candle=candle
            )
        
        return None
    
    @property
    def candles(self) -> List[Dict[str, Any]]:
        """Возвращает список свечей"""
        return self._candles
