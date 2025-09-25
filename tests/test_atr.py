#!/usr/bin/env python3
"""
Тесты для ATR индикатора
"""
import pytest
from robotlib.indicators.atr import IncrementalATR


class TestIncrementalATR:
    """Тесты для класса IncrementalATR"""
    
    def test_atr_initialization(self):
        """Тест инициализации ATR"""
        atr = IncrementalATR(period=14)
        
        assert atr._period == 14
        assert atr._prev_close is None
        assert atr._atr is None
        assert atr._warm_sum_tr == 0.0
        assert atr._warm_count == 0
        assert not atr.is_warm()
        assert atr.current() is None
    
    def test_atr_initialization_default_period(self):
        """Тест инициализации ATR с периодом по умолчанию"""
        atr = IncrementalATR()
        
        assert atr._period == 14  # Значение по умолчанию
        assert not atr.is_warm()
        assert atr.current() is None
    
    def test_atr_initialization_invalid_period(self):
        """Тест инициализации ATR с неверным периодом"""
        with pytest.raises(ValueError, match="период должен быть положительным"):
            IncrementalATR(period=0)
        
        with pytest.raises(ValueError, match="период должен быть положительным"):
            IncrementalATR(period=-5)
    
    def test_true_range_static_method_no_prev_close(self):
        """Тест статического метода _true_range без предыдущего закрытия"""
        tr = IncrementalATR._true_range(high=105.0, low=95.0, prev_close=None)
        assert tr == 10.0  # high - low
    
    def test_true_range_static_method_with_prev_close(self):
        """Тест статического метода _true_range с предыдущим закрытием"""
        # Случай 1: high - low максимальный
        tr = IncrementalATR._true_range(high=105.0, low=95.0, prev_close=100.0)
        assert tr == 10.0  # max(10.0, 5.0, 5.0)
        
        # Случай 2: high - prev_close максимальный
        tr = IncrementalATR._true_range(high=110.0, low=95.0, prev_close=100.0)
        assert tr == 15.0  # max(15.0, 10.0, 5.0) = 15.0
        
        # Случай 3: low - prev_close максимальный (отрицательный)
        tr = IncrementalATR._true_range(high=105.0, low=90.0, prev_close=100.0)
        assert tr == 15.0  # max(15.0, 5.0, 10.0) = 15.0
    
    def test_true_range_static_method_edge_cases(self):
        """Тест статического метода _true_range граничных случаев"""
        # Все значения одинаковые
        tr = IncrementalATR._true_range(high=100.0, low=100.0, prev_close=100.0)
        assert tr == 0.0
        
        # Предыдущее закрытие равно high
        tr = IncrementalATR._true_range(high=105.0, low=95.0, prev_close=105.0)
        assert tr == 10.0  # max(10.0, 0.0, 10.0)
        
        # Предыдущее закрытие равно low
        tr = IncrementalATR._true_range(high=105.0, low=95.0, prev_close=95.0)
        assert tr == 10.0  # max(10.0, 10.0, 0.0)
    
    def test_atr_warm_up_phase(self):
        """Тест фазы разогрева ATR"""
        atr = IncrementalATR(period=3)
        
        # Первые два обновления должны возвращать None
        result1 = atr.update(high=105.0, low=95.0, close=100.0)
        assert result1 is None
        assert not atr.is_warm()
        assert atr._warm_count == 1
        assert atr._warm_sum_tr == 10.0  # high - low
        
        result2 = atr.update(high=108.0, low=98.0, close=103.0)
        assert result2 is None
        assert not atr.is_warm()
        assert atr._warm_count == 2
        # TR2 = max(108-98, |108-100|, |98-100|) = max(10, 8, 2) = 10.0
        assert atr._warm_sum_tr == 20.0  # 10.0 + 10.0
        
        # Третье обновление должно вернуть первый ATR
        result3 = atr.update(high=110.0, low=100.0, close=105.0)
        assert result3 is not None
        assert atr.is_warm()
        # TR3 = max(110-100, |110-103|, |100-103|) = max(10, 7, 3) = 10.0
        assert result3 == 10.0  # (10.0 + 10.0 + 10.0) / 3 = 10.0
        assert atr.current() == 10.0
    
    def test_atr_wilder_smoothing(self):
        """Тест сглаживания Уайлдера после разогрева"""
        atr = IncrementalATR(period=3)
        
        # Разогреваем ATR
        atr.update(high=105.0, low=95.0, close=100.0)  # TR = 10.0
        atr.update(high=108.0, low=98.0, close=103.0)  # TR = 10.0
        atr.update(high=110.0, low=100.0, close=105.0)  # TR = 10.0, ATR = 10.0
        
        # Четвертое обновление - применяем формулу Уайлдера
        result4 = atr.update(high=112.0, low=102.0, close=107.0)  # TR = 10.0
        # ATR = (10.0 * (3-1) + 10.0) / 3 = (20.0 + 10.0) / 3 = 10.0
        expected_atr = (10.0 * 2 + 10.0) / 3.0
        assert abs(result4 - expected_atr) < 0.01
        assert atr.current() == result4
    
    def test_atr_sequence_of_updates(self):
        """Тест последовательности обновлений ATR"""
        atr = IncrementalATR(period=2)
        
        # Данные для тестирования
        test_data = [
            (105.0, 95.0, 100.0),  # TR = 10.0
            (108.0, 98.0, 103.0),  # TR = 10.0, ATR = 10.0
            (110.0, 100.0, 105.0), # TR = 10.0, ATR = 10.0
            (112.0, 102.0, 107.0), # TR = 10.0, ATR = 10.0
        ]
        
        results = []
        for high, low, close in test_data:
            result = atr.update(high, low, close)
            results.append(result)
        
        assert results[0] is None  # Первое обновление
        assert results[1] == 10.0  # Первый ATR: (10.0 + 10.0) / 2
        assert results[2] == 10.0  # (10.0 * 1 + 10.0) / 2
        assert results[3] == 10.0  # (10.0 * 1 + 10.0) / 2
    
    def test_atr_with_gap_up(self):
        """Тест ATR с гэпом вверх"""
        atr = IncrementalATR(period=2)
        
        # Первая свеча
        atr.update(high=105.0, low=95.0, close=100.0)  # TR = 10.0
        
        # Вторая свеча с гэпом вверх
        result = atr.update(high=120.0, low=110.0, close=115.0)  # TR = 20.0 (gap)
        assert result == 15.0  # (10.0 + 20.0) / 2
    
    def test_atr_with_gap_down(self):
        """Тест ATR с гэпом вниз"""
        atr = IncrementalATR(period=2)
        
        # Первая свеча
        atr.update(high=105.0, low=95.0, close=100.0)  # TR = 10.0
        
        # Вторая свеча с гэпом вниз
        result = atr.update(high=90.0, low=80.0, close=85.0)  # TR = 20.0 (gap)
        assert result == 15.0  # (10.0 + 20.0) / 2
    
    def test_atr_reset(self):
        """Тест сброса ATR"""
        atr = IncrementalATR(period=2)
        
        # Разогреваем ATR
        atr.update(high=105.0, low=95.0, close=100.0)
        atr.update(high=108.0, low=98.0, close=103.0)
        assert atr.is_warm()
        assert atr.current() is not None
        
        # Сбрасываем
        atr.reset()
        assert not atr.is_warm()
        assert atr.current() is None
        assert atr._prev_close is None
        assert atr._atr is None
        assert atr._warm_sum_tr == 0.0
        assert atr._warm_count == 0
    
    def test_atr_after_reset(self):
        """Тест ATR после сброса"""
        atr = IncrementalATR(period=2)
        
        # Разогреваем и сбрасываем
        atr.update(high=105.0, low=95.0, close=100.0)
        atr.update(high=108.0, low=98.0, close=103.0)
        atr.reset()
        
        # Начинаем заново
        result1 = atr.update(high=110.0, low=100.0, close=105.0)
        assert result1 is None
        
        result2 = atr.update(high=112.0, low=102.0, close=107.0)
        assert result2 is not None
        assert atr.is_warm()
    
    def test_atr_float_precision(self):
        """Тест точности вычислений с float"""
        atr = IncrementalATR(period=3)
        
        # Используем значения с плавающей точкой
        atr.update(high=105.5, low=95.5, close=100.5)
        atr.update(high=108.3, low=98.3, close=103.3)
        result = atr.update(high=110.7, low=100.7, close=105.7)
        
        assert result is not None
        assert isinstance(result, float)
        assert atr.is_warm()
    
    def test_atr_edge_case_zero_range(self):
        """Тест ATR с нулевым диапазоном"""
        atr = IncrementalATR(period=2)
        
        # Свечи с одинаковыми high, low, close
        atr.update(high=100.0, low=100.0, close=100.0)  # TR = 0.0
        result = atr.update(high=100.0, low=100.0, close=100.0)  # TR = 0.0
        
        assert result == 0.0
        assert atr.is_warm()
    
    def test_atr_large_period(self):
        """Тест ATR с большим периодом"""
        atr = IncrementalATR(period=100)
        
        # Первые 99 обновлений должны возвращать None
        for i in range(99):
            result = atr.update(high=100.0 + i, low=95.0 + i, close=97.0 + i)
            assert result is None
            assert not atr.is_warm()
        
        # 100-е обновление должно вернуть ATR
        result = atr.update(high=199.0, low=194.0, close=196.0)
        assert result is not None
        assert atr.is_warm()
        assert result > 0.0
    
    def test_atr_small_period(self):
        """Тест ATR с минимальным периодом"""
        atr = IncrementalATR(period=1)
        
        # Первое обновление должно сразу вернуть ATR
        result = atr.update(high=105.0, low=95.0, close=100.0)
        assert result == 10.0  # TR = high - low
        assert atr.is_warm()
        
        # Второе обновление
        result = atr.update(high=108.0, low=98.0, close=103.0)
        assert result == 10.0  # TR = max(108-98, |108-100|, |98-100|) = max(10, 8, 2) = 10.0
    
    def test_atr_negative_values(self):
        """Тест ATR с отрицательными значениями"""
        atr = IncrementalATR(period=2)
        
        # Используем отрицательные значения
        atr.update(high=-5.0, low=-15.0, close=-10.0)  # TR = 10.0
        result = atr.update(high=-2.0, low=-12.0, close=-7.0)  # TR = 10.0
        
        assert result == 10.0  # (10.0 + 10.0) / 2
        assert atr.is_warm()
    
    def test_atr_very_small_values(self):
        """Тест ATR с очень маленькими значениями"""
        atr = IncrementalATR(period=2)
        
        # Используем очень маленькие значения
        atr.update(high=0.0001, low=0.00005, close=0.000075)  # TR = 0.00005
        result = atr.update(high=0.0002, low=0.0001, close=0.00015)  # TR = 0.000125
        
        expected = (0.00005 + 0.000125) / 2.0
        assert abs(result - expected) < 1e-10
        assert atr.is_warm()
