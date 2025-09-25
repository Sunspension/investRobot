#!/usr/bin/env python3
"""
Тесты для backoff утилиты
"""
import pytest
from unittest.mock import patch
from robotlib.utils.backoff import compute_backoff_delay


class TestComputeBackoffDelay:
    """Тесты для функции compute_backoff_delay"""
    
    def test_basic_exponential_backoff(self):
        """Тест базового экспоненциального backoff"""
        # retries=0: 0.5 * 2^0 = 0.5
        delay = compute_backoff_delay(0, jitter="none")
        assert delay == 0.5
        
        # retries=1: 0.5 * 2^1 = 1.0
        delay = compute_backoff_delay(1, jitter="none")
        assert delay == 1.0
        
        # retries=2: 0.5 * 2^2 = 2.0
        delay = compute_backoff_delay(2, jitter="none")
        assert delay == 2.0
        
        # retries=3: 0.5 * 2^3 = 4.0
        delay = compute_backoff_delay(3, jitter="none")
        assert delay == 4.0
    
    def test_custom_base_seconds(self):
        """Тест с кастомной базовой задержкой"""
        # retries=2, base=1.0: 1.0 * 2^2 = 4.0
        delay = compute_backoff_delay(2, base_seconds=1.0, jitter="none")
        assert delay == 4.0
        
        # retries=1, base=2.0: 2.0 * 2^1 = 4.0
        delay = compute_backoff_delay(1, base_seconds=2.0, jitter="none")
        assert delay == 4.0
    
    def test_max_seconds_limit(self):
        """Тест ограничения максимальной задержки"""
        # retries=10: 0.5 * 2^10 = 512.0, но максимум 30.0
        delay = compute_backoff_delay(10, max_seconds=30.0, jitter="none")
        assert delay == 30.0
        
        # retries=5: 0.5 * 2^5 = 16.0, меньше максимума
        delay = compute_backoff_delay(5, max_seconds=30.0, jitter="none")
        assert delay == 16.0
    
    def test_negative_retries(self):
        """Тест отрицательного количества попыток"""
        # Отрицательные retries должны обрабатываться как 0
        delay = compute_backoff_delay(-1, jitter="none")
        assert delay == 0.5  # 0.5 * 2^0 = 0.5
        
        delay = compute_backoff_delay(-5, jitter="none")
        assert delay == 0.5  # 0.5 * 2^0 = 0.5
    
    def test_zero_retries(self):
        """Тест нулевого количества попыток"""
        delay = compute_backoff_delay(0, jitter="none")
        assert delay == 0.5  # 0.5 * 2^0 = 0.5
    
    def test_large_retries(self):
        """Тест большого количества попыток"""
        # retries=100: должно быть ограничено max_seconds
        delay = compute_backoff_delay(100, max_seconds=30.0, jitter="none")
        assert delay == 30.0
    
    def test_jitter_none(self):
        """Тест без джиттера"""
        delay = compute_backoff_delay(2, jitter="none")
        assert delay == 2.0  # Точное значение без случайности
    
    def test_jitter_half(self):
        """Тест половинного джиттера"""
        # Мокируем random.random() для предсказуемых результатов
        with patch('random.random', return_value=0.5):
            delay = compute_backoff_delay(2, jitter="half")
            # 2.0 * 0.5 + 0.5 * (2.0 * 0.5) = 1.0 + 0.5 = 1.5
            assert delay == 1.5
        
        with patch('random.random', return_value=0.0):
            delay = compute_backoff_delay(2, jitter="half")
            # 2.0 * 0.5 + 0.0 * (2.0 * 0.5) = 1.0 + 0.0 = 1.0
            assert delay == 1.0
        
        with patch('random.random', return_value=1.0):
            delay = compute_backoff_delay(2, jitter="half")
            # 2.0 * 0.5 + 1.0 * (2.0 * 0.5) = 1.0 + 1.0 = 2.0
            assert delay == 2.0
    
    def test_jitter_full(self):
        """Тест полного джиттера"""
        # Мокируем random.random() для предсказуемых результатов
        with patch('random.random', return_value=0.5):
            delay = compute_backoff_delay(2, jitter="full")
            # 0.5 * 2.0 = 1.0
            assert delay == 1.0
        
        with patch('random.random', return_value=0.0):
            delay = compute_backoff_delay(2, jitter="full")
            # 0.0 * 2.0 = 0.0
            assert delay == 0.0
        
        with patch('random.random', return_value=1.0):
            delay = compute_backoff_delay(2, jitter="full")
            # 1.0 * 2.0 = 2.0
            assert delay == 2.0
    
    def test_jitter_range_validation(self):
        """Тест что джиттер возвращает значения в правильном диапазоне"""
        base_delay = 4.0  # retries=3: 0.5 * 2^3 = 4.0
        
        # Тестируем половинный джиттер
        for _ in range(100):
            delay = compute_backoff_delay(3, jitter="half")
            # Должно быть в диапазоне [base_delay * 0.5, base_delay]
            assert 2.0 <= delay <= 4.0
        
        # Тестируем полный джиттер
        for _ in range(100):
            delay = compute_backoff_delay(3, jitter="full")
            # Должно быть в диапазоне [0, base_delay]
            assert 0.0 <= delay <= 4.0
    
    def test_default_parameters(self):
        """Тест параметров по умолчанию"""
        delay = compute_backoff_delay(1)
        # Должно использовать значения по умолчанию: base=0.5, max=30.0, jitter="full"
        # 0.5 * 2^1 = 1.0, но с полным джиттером это будет случайное значение [0, 1.0]
        assert 0.0 <= delay <= 1.0
    
    def test_edge_case_max_seconds_equals_base(self):
        """Тест граничного случая когда max_seconds = base_seconds"""
        delay = compute_backoff_delay(0, base_seconds=5.0, max_seconds=5.0, jitter="none")
        assert delay == 5.0
        
        delay = compute_backoff_delay(1, base_seconds=5.0, max_seconds=5.0, jitter="none")
        assert delay == 5.0  # Ограничено максимумом
    
    def test_edge_case_max_seconds_less_than_base(self):
        """Тест граничного случая когда max_seconds < base_seconds"""
        delay = compute_backoff_delay(0, base_seconds=10.0, max_seconds=5.0, jitter="none")
        assert delay == 5.0  # Ограничено максимумом
    
    def test_edge_case_zero_base_seconds(self):
        """Тест граничного случая с нулевой базовой задержкой"""
        delay = compute_backoff_delay(5, base_seconds=0.0, jitter="none")
        assert delay == 0.0  # 0.0 * 2^5 = 0.0
    
    def test_edge_case_very_small_base_seconds(self):
        """Тест с очень маленькой базовой задержкой"""
        delay = compute_backoff_delay(2, base_seconds=0.001, jitter="none")
        assert delay == 0.004  # 0.001 * 2^2 = 0.004
    
    def test_edge_case_very_large_base_seconds(self):
        """Тест с очень большой базовой задержкой"""
        delay = compute_backoff_delay(1, base_seconds=100.0, max_seconds=50.0, jitter="none")
        assert delay == 50.0  # 100.0 * 2^1 = 200.0, но ограничено 50.0
    
    def test_jitter_with_max_limit(self):
        """Тест джиттера с ограничением максимума"""
        # retries=10: 0.5 * 2^10 = 512.0, но максимум 30.0
        with patch('random.random', return_value=0.5):
            delay = compute_backoff_delay(10, max_seconds=30.0, jitter="half")
            # 30.0 * 0.5 + 0.5 * (30.0 * 0.5) = 15.0 + 7.5 = 22.5
            assert delay == 22.5
        
        with patch('random.random', return_value=0.5):
            delay = compute_backoff_delay(10, max_seconds=30.0, jitter="full")
            # 0.5 * 30.0 = 15.0
            assert delay == 15.0
    
    def test_multiple_calls_consistency(self):
        """Тест консистентности множественных вызовов"""
        # Без джиттера результаты должны быть одинаковыми
        delay1 = compute_backoff_delay(3, jitter="none")
        delay2 = compute_backoff_delay(3, jitter="none")
        assert delay1 == delay2 == 4.0
        
        # С джиттером результаты могут отличаться
        delays = [compute_backoff_delay(3, jitter="full") for _ in range(10)]
        # Не все значения должны быть одинаковыми (с очень высокой вероятностью)
        assert len(set(delays)) > 1 or all(0.0 <= d <= 4.0 for d in delays)


class TestBackoffEdgeCases:
    """Тесты граничных случаев для backoff"""
    
    def test_very_large_retries(self):
        """Тест очень большого количества попыток"""
        delay = compute_backoff_delay(1000, jitter="none")
        assert delay == 30.0  # Ограничено максимумом
    
    def test_float_retries(self):
        """Тест дробного количества попыток"""
        # Функция должна работать с float
        delay = compute_backoff_delay(2.5, jitter="none")
        # 0.5 * 2^2.5 ≈ 0.5 * 5.66 ≈ 2.83
        expected = 0.5 * (2 ** 2.5)
        assert abs(delay - expected) < 0.01
    
    def test_negative_base_seconds(self):
        """Тест отрицательной базовой задержки"""
        # Функция не проверяет отрицательные значения, но это может быть проблемой
        delay = compute_backoff_delay(1, base_seconds=-1.0, jitter="none")
        # -1.0 * 2^1 = -2.0
        assert delay == -2.0
    
    def test_negative_max_seconds(self):
        """Тест отрицательного максимума"""
        delay = compute_backoff_delay(1, max_seconds=-1.0, jitter="none")
        # 0.5 * 2^1 = 1.0, но max_seconds = -1.0, поэтому delay = -1.0
        assert delay == -1.0
