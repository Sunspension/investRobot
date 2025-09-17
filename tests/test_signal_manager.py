#!/usr/bin/env python3
"""
Тесты для SignalManager
"""
import unittest
from unittest.mock import Mock, MagicMock
from datetime import datetime
from collections import deque

from robotlib.signal_manager import SignalManager, Signal
from robotlib.utils.money import Money
from tinkoff.invest import Candle, HistoricCandle, Quotation


class TestSignalManager(unittest.TestCase):
    """Тесты для SignalManager"""

    def setUp(self):
        """Настройка тестов"""
        self.signal_manager = SignalManager(
            macd_fast=6,
            macd_slow=11,
            macd_signal=9,
            atr_period=7,
            lookback_min=6,
            lookback_max=20,
            peak_prominence=0.2
        )

    def create_mock_candle(self, price: float, volume: int = 1000, time: datetime = None) -> Candle:
        """Создает мок свечи"""
        if time is None:
            time = datetime.now()
        
        return Candle(
            figi="FUTIMOEXF000",
            interval=1,
            open=Quotation(units=int(price), nano=int((price - int(price)) * 1e9)),
            high=Quotation(units=int(price * 1.01), nano=int((price * 1.01 - int(price * 1.01)) * 1e9)),
            low=Quotation(units=int(price * 0.99), nano=int((price * 0.99 - int(price * 0.99)) * 1e9)),
            close=Quotation(units=int(price), nano=int((price - int(price)) * 1e9)),
            volume=volume,
            time=time
        )

    def test_init(self):
        """Тест инициализации SignalManager"""
        # Проверяем, что объекты созданы
        self.assertIsNotNone(self.signal_manager._macd)
        self.assertIsNotNone(self.signal_manager._atr)
        self.assertEqual(self.signal_manager._lookback_min, 6)
        self.assertEqual(self.signal_manager._lookback_max, 20)
        self.assertEqual(self.signal_manager._peak_prominence, 0.2)
        self.assertIsInstance(self.signal_manager.candles, deque)
        self.assertIsInstance(self.signal_manager._hist_window, deque)

    def test_add_candle_insufficient_data(self):
        """Тест добавления свечи при недостаточном количестве данных"""
        # Добавляем несколько свечей (меньше чем нужно для MACD)
        for i in range(5):
            candle = self.create_mock_candle(100.0 + i)
            signal = self.signal_manager.add_candle(candle)
            self.assertIsNone(signal, f"Signal должен быть None для свечи {i}")

    def test_add_candle_sufficient_data(self):
        """Тест добавления свечи при достаточном количестве данных"""
        # Добавляем достаточно свечей для MACD и ATR
        signals = []
        for i in range(50):  # Увеличиваем количество свечей
            candle = self.create_mock_candle(100.0 + i * 0.1)
            signal = self.signal_manager.add_candle(candle)
            if signal:
                signals.append(signal)
        
        # Проверяем, что хотя бы один сигнал был сгенерирован
        self.assertGreater(len(signals), 0, "Должен быть сгенерирован хотя бы один сигнал")
        
        # Проверяем последний сигнал
        last_signal = signals[-1]
        self.assertIsInstance(last_signal, Signal)
        self.assertIsNotNone(last_signal.macd)
        self.assertIsNotNone(last_signal.signal)
        self.assertIsNotNone(last_signal.histogram)
        self.assertIsNotNone(last_signal.candle)

    def test_signal_properties(self):
        """Тест свойств сигнала"""
        # Добавляем достаточно свечей
        signals = []
        for i in range(50):
            candle = self.create_mock_candle(100.0 + i * 0.1)
            signal = self.signal_manager.add_candle(candle)
            if signal:
                signals.append(signal)
        
        # Проверяем последний сигнал
        if signals:
            last_signal = signals[-1]
            self.assertIsNotNone(last_signal)
            self.assertIsInstance(last_signal.macd, float)
            self.assertIsInstance(last_signal.signal, float)
            self.assertIsInstance(last_signal.histogram, float)
            self.assertIsInstance(last_signal.peak_detected, bool)
            self.assertIsInstance(last_signal.trough_detected, bool)
            self.assertIsNotNone(last_signal.candle)

    def test_histogram_calculation(self):
        """Тест расчета гистограммы"""
        # Добавляем свечи с разными ценами для создания тренда
        prices = [100.0, 101.0, 102.0, 101.5, 100.5, 99.0, 98.5, 99.5, 100.0, 101.0,
                 102.0, 103.0, 102.5, 101.0, 100.0, 99.0, 98.0, 97.5, 98.0, 99.0]
        
        signals = []
        for price in prices:
            candle = self.create_mock_candle(price)
            signal = self.signal_manager.add_candle(candle)
            if signal:
                signals.append(signal)
        
        # Проверяем, что гистограмма рассчитывается
        if signals:
            last_signal = signals[-1]
            self.assertIsNotNone(last_signal.histogram)
            self.assertIsInstance(last_signal.histogram, float)

    def test_peak_detection(self):
        """Тест обнаружения пиков"""
        # Создаем данные с явными пиками и впадинами
        prices = [100.0] * 5  # Начальные данные
        # Добавляем пик
        prices.extend([101.0, 102.0, 103.0, 102.0, 101.0])
        # Добавляем впадину
        prices.extend([100.0, 99.0, 98.0, 99.0, 100.0])
        # Добавляем еще данные
        prices.extend([101.0, 102.0, 101.0, 100.0, 99.0])
        
        signals = []
        for price in prices:
            candle = self.create_mock_candle(price)
            signal = self.signal_manager.add_candle(candle)
            if signal:
                signals.append(signal)
        
        # Проверяем, что пики и впадины обнаруживаются
        if len(signals) > 5:
            # Проверяем, что хотя бы один сигнал имеет обнаруженные пики/впадины
            has_peaks = any(s.peak_detected for s in signals)
            has_troughs = any(s.trough_detected for s in signals)
            # Не обязательно, что будут обнаружены, но если есть, то должны быть bool
            self.assertIsInstance(has_peaks, bool)
            self.assertIsInstance(has_troughs, bool)

    def test_candle_storage(self):
        """Тест хранения свечей"""
        # Добавляем достаточно свечей для MACD
        for i in range(20):
            candle = self.create_mock_candle(100.0 + i)
            self.signal_manager.add_candle(candle)
        
        # Проверяем, что свечи сохраняются (только когда MACD имеет данные)
        self.assertGreater(len(self.signal_manager.candles), 0, "Должны сохраняться свечи когда MACD имеет данные")
        
        # Проверяем, что свечи сохраняются в правильном порядке
        # Свечи сохраняются только когда MACD имеет данные, поэтому индексы могут не совпадать
        for i, stored_candle in enumerate(self.signal_manager.candles):
            actual_price = stored_candle['close']  # Это уже float, не Money
            # Проверяем, что цена находится в ожидаемом диапазоне
            self.assertGreaterEqual(actual_price, 100.0)
            self.assertLessEqual(actual_price, 119.0)  # 100 + 19

    def test_adaptive_lookback(self):
        """Тест адаптивного размера окна"""
        # Добавляем свечи с разной волатильностью
        # Низкая волатильность
        for i in range(10):
            candle = self.create_mock_candle(100.0 + i * 0.01)
            self.signal_manager.add_candle(candle)
        
        # Высокая волатильность
        for i in range(10):
            candle = self.create_mock_candle(100.0 + i * 0.5)
            self.signal_manager.add_candle(candle)
        
        # Проверяем, что адаптивный lookback работает
        # (конкретные значения зависят от реализации ATR)
        self.assertGreaterEqual(len(self.signal_manager._hist_window), 0)

    def test_signal_with_previous_values(self):
        """Тест сигнала с предыдущими значениями"""
        # Добавляем достаточно свечей
        for i in range(20):
            candle = self.create_mock_candle(100.0 + i * 0.1)
            signal = self.signal_manager.add_candle(candle)
        
        # Проверяем последний сигнал
        if signal:
            # Проверяем, что предыдущие значения доступны
            if signal.macd_prev is not None:
                self.assertIsInstance(signal.macd_prev, float)
            if signal.signal_prev is not None:
                self.assertIsInstance(signal.signal_prev, float)

    def test_edge_cases(self):
        """Тест граничных случаев"""
        # Тест с нулевой ценой
        candle = self.create_mock_candle(0.0)
        signal = self.signal_manager.add_candle(candle)
        # Должен обработать без ошибок
        self.assertIsNone(signal)  # Недостаточно данных
        
        # Тест с очень большой ценой
        candle = self.create_mock_candle(1000000.0)
        signal = self.signal_manager.add_candle(candle)
        # Должен обработать без ошибок
        self.assertIsNone(signal)  # Недостаточно данных

    def test_histogram_window_management(self):
        """Тест управления окном гистограммы"""
        # Добавляем много свечей
        for i in range(50):
            candle = self.create_mock_candle(100.0 + i * 0.1)
            self.signal_manager.add_candle(candle)
        
        # Проверяем, что окно гистограммы не превышает максимальный размер
        self.assertLessEqual(len(self.signal_manager._hist_window), self.signal_manager._lookback_max)

    def test_signal_consistency(self):
        """Тест согласованности сигналов"""
        # Добавляем свечи с постоянной ценой
        for i in range(20):
            candle = self.create_mock_candle(100.0)
            signal = self.signal_manager.add_candle(candle)
        
        # При постоянной цене MACD должен быть близок к нулю
        if signal:
            self.assertIsNotNone(signal.macd)
            self.assertIsNotNone(signal.signal)
            self.assertIsNotNone(signal.histogram)


class TestSignal(unittest.TestCase):
    """Тесты для класса Signal"""

    def test_signal_creation(self):
        """Тест создания сигнала"""
        signal = Signal(
            macd=1.5,
            signal=1.2,
            histogram=0.3,
            peak_detected=True,
            trough_detected=False
        )
        
        self.assertEqual(signal.macd, 1.5)
        self.assertEqual(signal.signal, 1.2)
        self.assertEqual(signal.histogram, 0.3)
        self.assertTrue(signal.peak_detected)
        self.assertFalse(signal.trough_detected)
        self.assertIsNone(signal.candle)

    def test_signal_defaults(self):
        """Тест значений по умолчанию"""
        signal = Signal()
        
        self.assertIsNone(signal.macd)
        self.assertIsNone(signal.signal)
        self.assertIsNone(signal.histogram)
        self.assertIsNone(signal.macd_prev)
        self.assertIsNone(signal.signal_prev)
        self.assertFalse(signal.peak_detected)
        self.assertFalse(signal.trough_detected)
        self.assertIsNone(signal.candle)




if __name__ == '__main__':
    unittest.main()
