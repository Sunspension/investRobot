import pytest
from robotlib.indicators.ema import IncrementalEMA


class TestIncrementalEMA:
    def test_ema_initialization(self):
        """Тест инициализации EMA"""
        ema = IncrementalEMA(period=10)
        assert ema._period == 10
        assert ema._alpha == 2.0 / 11.0  # 2/(10+1)
        assert ema._ema is None
        assert ema._warm_count == 0
        assert ema._warm_sum == 0.0

    def test_ema_initialization_invalid_period(self):
        """Тест инициализации EMA с невалидным периодом"""
        with pytest.raises(ValueError, match="период должен быть положительным"):
            IncrementalEMA(period=0)
        with pytest.raises(ValueError, match="период должен быть положительным"):
            IncrementalEMA(period=-5)

    def test_ema_warm_up_phase(self):
        """Тест фазы разогрева EMA"""
        ema = IncrementalEMA(period=3)

        # Первые два обновления должны возвращать None
        result1 = ema.update(100.0)
        assert result1 is None
        assert not ema.is_warm()
        assert ema._warm_count == 1
        assert ema._warm_sum == 100.0

        result2 = ema.update(102.0)
        assert result2 is None
        assert not ema.is_warm()
        assert ema._warm_count == 2
        assert ema._warm_sum == 202.0  # 100.0 + 102.0

        # Третье обновление должно вернуть первый EMA (SMA)
        result3 = ema.update(104.0)
        assert result3 is not None
        assert ema.is_warm()
        assert result3 == 102.0  # (100.0 + 102.0 + 104.0) / 3 = 102.0
        assert ema.current() == 102.0

    def test_ema_recurrence_formula(self):
        """Тест рекуррентной формулы EMA после разогрева"""
        ema = IncrementalEMA(period=3)

        # Разогреваем EMA
        ema.update(100.0)  # warm_sum = 100.0
        ema.update(102.0)  # warm_sum = 202.0
        ema.update(104.0)  # ema = 102.0 (SMA)

        # Четвертое обновление - применяем формулу EMA
        result4 = ema.update(106.0)
        # alpha = 2/(3+1) = 0.5
        # ema = (106.0 - 102.0) * 0.5 + 102.0 = 4.0 * 0.5 + 102.0 = 104.0
        expected_ema = (106.0 - 102.0) * 0.5 + 102.0
        assert abs(result4 - expected_ema) < 0.01
        assert ema.current() == result4

    def test_ema_sequence_of_updates(self):
        """Тест последовательности обновлений EMA"""
        ema = IncrementalEMA(period=2)

        # Данные для тестирования
        test_data = [100.0, 102.0, 104.0, 106.0, 108.0]

        results = []
        for value in test_data:
            result = ema.update(value)
            results.append(result)

        assert results[0] is None  # Первое обновление
        assert results[1] == 101.0  # Первый EMA: (100.0 + 102.0) / 2
        # alpha = 2/(2+1) = 2/3
        assert results[2] == 103.0  # (104.0 - 101.0) * 2/3 + 101.0 = 3.0 * 2/3 + 101.0 = 103.0
        assert results[3] == 105.0  # (106.0 - 103.0) * 2/3 + 103.0 = 3.0 * 2/3 + 103.0 = 105.0
        assert results[4] == 107.0  # (108.0 - 105.0) * 2/3 + 105.0 = 3.0 * 2/3 + 105.0 = 107.0

    def test_ema_with_constant_values(self):
        """Тест EMA с постоянными значениями"""
        ema = IncrementalEMA(period=3)

        # Разогреваем с постоянными значениями
        ema.update(100.0)
        ema.update(100.0)
        result = ema.update(100.0)
        assert result == 100.0  # SMA = 100.0

        # Продолжаем с постоянными значениями
        result = ema.update(100.0)
        assert result == 100.0  # EMA остается 100.0

    def test_ema_with_trending_up(self):
        """Тест EMA с восходящим трендом"""
        ema = IncrementalEMA(period=2)

        ema.update(100.0)
        ema.update(102.0)  # ema = 101.0

        # Продолжаем восходящий тренд
        result = ema.update(104.0)
        # alpha = 2/3
        # ema = (104.0 - 101.0) * 2/3 + 101.0 = 3.0 * 2/3 + 101.0 = 103.0
        assert result == 103.0

    def test_ema_with_trending_down(self):
        """Тест EMA с нисходящим трендом"""
        ema = IncrementalEMA(period=2)

        ema.update(100.0)
        ema.update(98.0)  # ema = 99.0

        # Продолжаем нисходящий тренд
        result = ema.update(96.0)
        # alpha = 2/3
        # ema = (96.0 - 99.0) * 2/3 + 99.0 = -3.0 * 2/3 + 99.0 = 97.0
        assert result == 97.0

    def test_ema_reset(self):
        """Тест сброса EMA"""
        ema = IncrementalEMA(period=2)
        ema.update(100.0)
        ema.update(102.0)
        assert ema.is_warm()
        ema.reset()
        assert not ema.is_warm()
        assert ema.current() is None
        assert ema._warm_count == 0
        assert ema._warm_sum == 0.0

    def test_ema_after_reset(self):
        """Тест EMA после сброса"""
        ema = IncrementalEMA(period=2)
        ema.update(100.0)
        ema.update(102.0)
        ema.reset()
        result1 = ema.update(104.0)
        assert result1 is None
        result2 = ema.update(106.0)
        assert result2 == 105.0  # (104.0 + 106.0) / 2

    def test_ema_float_precision(self):
        """Тест точности float для EMA"""
        ema = IncrementalEMA(period=2)
        ema.update(100.1)
        ema.update(100.3)  # ema = 100.2
        result = ema.update(100.5)
        # alpha = 2/3
        # ema = (100.5 - 100.2) * 2/3 + 100.2 = 0.3 * 2/3 + 100.2 = 100.4
        expected_ema = 100.4
        assert abs(result - expected_ema) < 1e-9

    def test_ema_edge_case_zero_values(self):
        """Тест EMA с нулевыми значениями"""
        ema = IncrementalEMA(period=2)
        ema.update(0.0)
        result = ema.update(0.0)
        assert result == 0.0

    def test_ema_large_period(self):
        """Тест EMA с большим периодом"""
        ema = IncrementalEMA(period=100)
        for i in range(99):
            ema.update(100.0 + i)
            assert ema.current() is None
        result = ema.update(100.0 + 99)
        assert result is not None
        assert ema.is_warm()
        assert result > 0.0

    def test_ema_small_period(self):
        """Тест EMA с минимальным периодом"""
        ema = IncrementalEMA(period=1)

        # Первое обновление должно сразу вернуть EMA
        result = ema.update(100.0)
        assert result == 100.0  # SMA = 100.0
        assert ema.is_warm()

        # Второе обновление
        result = ema.update(102.0)
        # alpha = 2/(1+1) = 1.0
        # ema = (102.0 - 100.0) * 1.0 + 100.0 = 102.0
        assert result == 102.0

    def test_ema_negative_values(self):
        """Тест EMA с отрицательными значениями"""
        ema = IncrementalEMA(period=2)

        ema.update(-100.0)
        result = ema.update(-98.0)
        assert result == -99.0  # (-100.0 + (-98.0)) / 2

    def test_ema_very_small_values(self):
        """Тест EMA с очень маленькими значениями"""
        ema = IncrementalEMA(period=2)

        ema.update(0.0001)
        result = ema.update(0.0002)
        expected = (0.0001 + 0.0002) / 2.0
        assert abs(result - expected) < 1e-10

    def test_ema_alpha_calculation(self):
        """Тест правильности расчета alpha"""
        ema = IncrementalEMA(period=5)
        assert ema._alpha == 2.0 / 6.0  # 2/(5+1)

        ema = IncrementalEMA(period=10)
        assert ema._alpha == 2.0 / 11.0  # 2/(10+1)

        ema = IncrementalEMA(period=1)
        assert ema._alpha == 2.0 / 2.0  # 2/(1+1) = 1.0

    def test_ema_convergence(self):
        """Тест сходимости EMA к постоянному значению"""
        ema = IncrementalEMA(period=5)

        # Разогреваем
        for i in range(5):
            ema.update(100.0)

        # Продолжаем с постоянным значением
        for i in range(10):
            result = ema.update(100.0)
            assert result == 100.0

    def test_ema_response_to_change(self):
        """Тест отклика EMA на изменение"""
        ema = IncrementalEMA(period=3)

        # Разогреваем с постоянным значением
        for i in range(3):
            ema.update(100.0)

        # Резкое изменение
        result = ema.update(200.0)
        # alpha = 2/4 = 0.5
        # ema = (200.0 - 100.0) * 0.5 + 100.0 = 150.0
        assert result == 150.0

        # Еще одно изменение
        result = ema.update(200.0)
        # ema = (200.0 - 150.0) * 0.5 + 150.0 = 175.0
        assert result == 175.0

    def test_ema_oscillation(self):
        """Тест EMA с осцилляцией"""
        ema = IncrementalEMA(period=2)

        ema.update(100.0)
        ema.update(102.0)  # ema = 101.0

        # Осцилляция
        result1 = ema.update(100.0)  # Вниз
        result2 = ema.update(102.0)  # Вверх
        result3 = ema.update(100.0)  # Вниз

        # alpha = 2/3
        # result1 = (100.0 - 101.0) * 2/3 + 101.0 = 100.33
        # result2 = (102.0 - 100.33) * 2/3 + 100.33 = 101.44
        # result3 = (100.0 - 101.44) * 2/3 + 101.44 = 100.48

        assert result1 == pytest.approx(100.33, abs=0.01)
        assert result2 == pytest.approx(101.44, abs=0.01)
        assert result3 == pytest.approx(100.48, abs=0.01)
