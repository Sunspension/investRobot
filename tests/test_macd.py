import pytest
from robotlib.indicators.macd import IncrementalMACD
from robotlib.indicators.base import MACDPoint


class TestIncrementalMACD:
    def test_macd_initialization(self):
        """Тест инициализации MACD"""
        macd = IncrementalMACD(fast_period=12, slow_period=26, signal_period=9)
        assert macd._ema_fast._period == 12
        assert macd._ema_slow._period == 26
        assert macd._ema_signal._period == 9
        assert macd._last is None

    def test_macd_initialization_default_periods(self):
        """Тест инициализации MACD с параметрами по умолчанию"""
        macd = IncrementalMACD()
        assert macd._ema_fast._period == 12
        assert macd._ema_slow._period == 26
        assert macd._ema_signal._period == 9

    def test_macd_initialization_invalid_periods(self):
        """Тест инициализации MACD с невалидными периодами"""
        with pytest.raises(ValueError, match="периоды должны быть положительными"):
            IncrementalMACD(fast_period=0, slow_period=26, signal_period=9)
        with pytest.raises(ValueError, match="периоды должны быть положительными"):
            IncrementalMACD(fast_period=12, slow_period=0, signal_period=9)
        with pytest.raises(ValueError, match="периоды должны быть положительными"):
            IncrementalMACD(fast_period=12, slow_period=26, signal_period=0)

    def test_macd_initialization_fast_greater_than_slow(self):
        """Тест инициализации MACD когда fast_period >= slow_period"""
        with pytest.raises(ValueError, match="fast_period должен быть меньше slow_period"):
            IncrementalMACD(fast_period=26, slow_period=26, signal_period=9)
        with pytest.raises(ValueError, match="fast_period должен быть меньше slow_period"):
            IncrementalMACD(fast_period=30, slow_period=26, signal_period=9)

    def test_macd_warm_up_phase(self):
        """Тест фазы разогрева MACD"""
        macd = IncrementalMACD(fast_period=2, slow_period=3, signal_period=2)

        # Первые обновления должны возвращать None
        for i in range(3):  # До разогрева slow EMA
            result = macd.update(100.0 + i)
            assert result is None
            assert not macd.is_warm()

        # Четвертое обновление - все EMA разогреты, MACD готов
        result = macd.update(103.0)
        assert result is not None
        assert isinstance(result, MACDPoint)
        assert macd.is_warm()

    def test_macd_calculation(self):
        """Тест расчета MACD"""
        macd = IncrementalMACD(fast_period=2, slow_period=3, signal_period=2)

        # Разогреваем все EMA
        macd.update(100.0)  # fast: None, slow: None, signal: None
        macd.update(102.0)  # fast: 101.0, slow: None, signal: None
        macd.update(104.0)  # fast: 103.0, slow: 102.0, signal: None
        macd.update(106.0)  # fast: 105.0, slow: 104.0, signal: None
        result = macd.update(108.0)  # fast: 107.0, slow: 106.0, signal: 1.0

        # macd_line = 107.0 - 106.0 = 1.0
        # signal = 1.0 (SMA от macd_line)
        # histogram = 1.0 - 1.0 = 0.0
        assert result.macd == 1.0
        assert result.signal == 1.0
        assert result.histogram == 0.0

    def test_macd_sequence_of_updates(self):
        """Тест последовательности обновлений MACD"""
        macd = IncrementalMACD(fast_period=2, slow_period=3, signal_period=2)

        # Данные для тестирования
        test_data = [100.0, 102.0, 104.0, 106.0, 108.0, 110.0]

        results = []
        for value in test_data:
            result = macd.update(value)
            results.append(result)

        # Первые 3 обновления должны возвращать None
        for i in range(3):
            assert results[i] is None

        # 4-е обновление - первый MACD
        assert results[3] is not None
        assert isinstance(results[3], MACDPoint)

        # 5-е и 6-е обновления - следующие MACD
        assert results[4] is not None
        assert isinstance(results[4], MACDPoint)
        assert results[5] is not None
        assert isinstance(results[5], MACDPoint)

    def test_macd_with_trending_up(self):
        """Тест MACD с восходящим трендом"""
        macd = IncrementalMACD(fast_period=2, slow_period=3, signal_period=2)

        # Разогреваем
        for i in range(3):
            macd.update(100.0 + i * 2)  # 100, 102, 104

        # Продолжаем восходящий тренд
        result1 = macd.update(106.0)
        result2 = macd.update(108.0)

        # При восходящем тренде MACD должен быть положительным
        assert result1.macd > 0
        assert result2.macd > 0
        # При постоянном тренде MACD остается постоянным
        assert result2.macd == result1.macd

    def test_macd_with_trending_down(self):
        """Тест MACD с нисходящим трендом"""
        macd = IncrementalMACD(fast_period=2, slow_period=3, signal_period=2)

        # Разогреваем
        for i in range(3):
            macd.update(110.0 - i * 2)  # 110, 108, 106

        # Продолжаем нисходящий тренд
        result1 = macd.update(104.0)
        result2 = macd.update(102.0)

        # При нисходящем тренде MACD должен быть отрицательным
        assert result1.macd < 0
        assert result2.macd < 0
        # При постоянном тренде MACD остается постоянным
        assert result2.macd == result1.macd

    def test_macd_with_constant_values(self):
        """Тест MACD с постоянными значениями"""
        macd = IncrementalMACD(fast_period=2, slow_period=3, signal_period=2)

        # Разогреваем с постоянными значениями
        for i in range(4):
            macd.update(100.0)

        # Продолжаем с постоянным значением
        result = macd.update(100.0)

        # При постоянных значениях MACD должен быть близок к нулю
        assert abs(result.macd) < 0.01
        assert abs(result.signal) < 0.01
        assert abs(result.histogram) < 0.01

    def test_macd_reset(self):
        """Тест сброса MACD"""
        macd = IncrementalMACD(fast_period=2, slow_period=3, signal_period=2)

        # Разогреваем
        for i in range(5):
            macd.update(100.0 + i)
        assert macd.is_warm()

        # Сбрасываем
        macd.reset()
        assert not macd.is_warm()
        assert macd.current() is None
        assert macd._last is None

    def test_macd_after_reset(self):
        """Тест MACD после сброса"""
        macd = IncrementalMACD(fast_period=2, slow_period=3, signal_period=2)

        # Разогреваем и сбрасываем
        for i in range(4):
            macd.update(100.0 + i)
        macd.reset()

        # Разогреваем заново
        for i in range(3):
            result = macd.update(200.0 + i)
            assert result is None
        result = macd.update(203.0)
        assert result is not None
        assert macd.is_warm()

    def test_macd_float_precision(self):
        """Тест точности float для MACD"""
        macd = IncrementalMACD(fast_period=2, slow_period=3, signal_period=2)

        # Разогреваем с точными значениями
        for i in range(4):
            macd.update(100.1 + i * 0.1)

        result = macd.update(100.5)
        assert isinstance(result, MACDPoint)
        assert isinstance(result.macd, float)
        assert isinstance(result.signal, float)
        assert isinstance(result.histogram, float)

    def test_macd_edge_case_zero_values(self):
        """Тест MACD с нулевыми значениями"""
        macd = IncrementalMACD(fast_period=2, slow_period=3, signal_period=2)

        # Разогреваем с нулевыми значениями
        for i in range(4):
            macd.update(0.0)

        result = macd.update(0.0)
        assert result.macd == 0.0
        assert result.signal == 0.0
        assert result.histogram == 0.0

    def test_macd_large_periods(self):
        """Тест MACD с большими периодами"""
        macd = IncrementalMACD(fast_period=10, slow_period=20, signal_period=5)

        # Разогреваем
        for i in range(23):  # До разогрева signal EMA
            result = macd.update(100.0 + i)
            assert result is None

        # 24-е обновление - signal EMA разогрета, MACD готов
        result = macd.update(123.0)
        assert result is not None
        assert macd.is_warm()

    def test_macd_small_periods(self):
        """Тест MACD с минимальными периодами"""
        macd = IncrementalMACD(fast_period=1, slow_period=2, signal_period=1)

        # Разогреваем
        macd.update(100.0)  # fast: 100.0, slow: None, signal: None
        macd.update(102.0)  # fast: 102.0, slow: 101.0, signal: None
        result = macd.update(104.0)  # fast: 104.0, slow: 103.0, signal: 1.0

        # macd_line = 104.0 - 103.0 = 1.0
        # signal = 1.0 (SMA от macd_line)
        # histogram = 1.0 - 1.0 = 0.0
        assert result.macd == 1.0
        assert result.signal == 1.0
        assert result.histogram == 0.0

    def test_macd_negative_values(self):
        """Тест MACD с отрицательными значениями"""
        macd = IncrementalMACD(fast_period=2, slow_period=3, signal_period=2)

        # Разогреваем с отрицательными значениями
        for i in range(4):
            macd.update(-100.0 - i)

        result = macd.update(-104.0)
        assert isinstance(result, MACDPoint)
        # MACD может быть положительным или отрицательным в зависимости от тренда

    def test_macd_very_small_values(self):
        """Тест MACD с очень маленькими значениями"""
        macd = IncrementalMACD(fast_period=2, slow_period=3, signal_period=2)

        # Разогреваем с очень маленькими значениями
        for i in range(3):
            macd.update(0.0001 + i * 0.0001)

        result = macd.update(0.0004)
        assert isinstance(result, MACDPoint)
        assert abs(result.macd) < 1e-4
        assert abs(result.signal) < 1e-4
        assert abs(result.histogram) < 1e-4

    def test_macd_histogram_calculation(self):
        """Тест расчета гистограммы MACD"""
        macd = IncrementalMACD(fast_period=2, slow_period=3, signal_period=2)

        # Разогреваем
        for i in range(4):
            macd.update(100.0 + i)

        result = macd.update(104.0)
        # histogram = macd_line - signal
        expected_histogram = result.macd - result.signal
        assert result.histogram == expected_histogram

    def test_macd_signal_line_calculation(self):
        """Тест расчета сигнальной линии MACD"""
        macd = IncrementalMACD(fast_period=2, slow_period=3, signal_period=2)

        # Разогреваем
        for i in range(4):
            macd.update(100.0 + i)

        result1 = macd.update(104.0)
        result2 = macd.update(105.0)

        # Сигнальная линия должна сглаживать MACD линию
        assert isinstance(result1.signal, float)
        assert isinstance(result2.signal, float)

    def test_macd_convergence(self):
        """Тест сходимости MACD к постоянному значению"""
        macd = IncrementalMACD(fast_period=2, slow_period=3, signal_period=2)

        # Разогреваем
        for i in range(4):
            macd.update(100.0)

        # Продолжаем с постоянным значением
        results = []
        for i in range(10):
            result = macd.update(100.0)
            results.append(result)

        # MACD должен сходиться к нулю при постоянных значениях
        for result in results:
            assert abs(result.macd) < 0.01
            assert abs(result.signal) < 0.01
            assert abs(result.histogram) < 0.01

    def test_macd_response_to_change(self):
        """Тест отклика MACD на изменение"""
        macd = IncrementalMACD(fast_period=2, slow_period=3, signal_period=2)

        # Разогреваем с постоянным значением
        for i in range(4):
            macd.update(100.0)

        # Резкое изменение
        result = macd.update(200.0)
        # MACD должен отреагировать на изменение
        assert abs(result.macd) > 0.01

    def test_macd_oscillation(self):
        """Тест MACD с осцилляцией"""
        macd = IncrementalMACD(fast_period=2, slow_period=3, signal_period=2)

        # Разогреваем
        for i in range(4):
            macd.update(100.0 + i)

        # Осцилляция
        result1 = macd.update(100.0)  # Вниз
        result2 = macd.update(110.0)  # Вверх
        result3 = macd.update(100.0)  # Вниз

        # MACD должен отражать изменения
        assert isinstance(result1, MACDPoint)
        assert isinstance(result2, MACDPoint)
        assert isinstance(result3, MACDPoint)

    def test_macd_current_method(self):
        """Тест метода current()"""
        macd = IncrementalMACD(fast_period=2, slow_period=3, signal_period=2)

        # До разогрева
        assert macd.current() is None

        # Разогреваем
        for i in range(3):
            macd.update(100.0 + i)
            assert macd.current() is None

        # После разогрева
        result = macd.update(103.0)
        assert macd.current() is result
        assert macd.current() is not None

    def test_macd_is_warm_method(self):
        """Тест метода is_warm()"""
        macd = IncrementalMACD(fast_period=2, slow_period=3, signal_period=2)

        # До разогрева
        assert not macd.is_warm()

        # Разогреваем по частям
        macd.update(100.0)  # fast: None, slow: None, signal: None
        assert not macd.is_warm()

        macd.update(102.0)  # fast: 101.0, slow: None, signal: None
        assert not macd.is_warm()

        macd.update(104.0)  # fast: 103.0, slow: 102.0, signal: None
        assert not macd.is_warm()

        macd.update(106.0)  # fast: 105.0, slow: 104.0, signal: 1.0
        assert macd.is_warm()
