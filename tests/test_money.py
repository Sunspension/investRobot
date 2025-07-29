#!/usr/bin/env python3
"""
Тесты для класса Money
"""
import unittest
import math
from unittest.mock import Mock

from robotlib.utils.money import Money
from tinkoff.invest import MoneyValue, Quotation


class TestMoney(unittest.TestCase):
    """Тесты для класса Money"""

    def test_init_from_int(self):
        """Тест инициализации из int"""
        money = Money(100)
        self.assertEqual(money.units, 100)
        self.assertEqual(money.nano, 0)
        self.assertEqual(float(money), 100.0)

    def test_init_from_float(self):
        """Тест инициализации из float"""
        money = Money(100.5)
        self.assertEqual(money.units, 100)
        self.assertEqual(money.nano, 500000000)  # 0.5 * 10^9
        self.assertAlmostEqual(float(money), 100.5, places=9)

    def test_init_from_float_with_precision(self):
        """Тест инициализации из float с высокой точностью"""
        money = Money(100.123456789)
        self.assertEqual(money.units, 100)
        self.assertEqual(money.nano, 123456789)
        self.assertAlmostEqual(float(money), 100.123456789, places=9)

    def test_init_from_quotation(self):
        """Тест инициализации из Quotation"""
        quotation = Quotation(units=100, nano=500000000)
        money = Money(quotation)
        self.assertEqual(money.units, 100)
        self.assertEqual(money.nano, 500000000)
        self.assertAlmostEqual(float(money), 100.5, places=9)

    def test_init_from_money_value(self):
        """Тест инициализации из MoneyValue"""
        money_value = MoneyValue(currency="rub", units=100, nano=500000000)
        money = Money(money_value)
        self.assertEqual(money.units, 100)
        self.assertEqual(money.nano, 500000000)
        self.assertAlmostEqual(float(money), 100.5, places=9)

    def test_init_with_nano(self):
        """Тест инициализации с явным указанием nano"""
        money = Money(100, nano=500000000)
        self.assertEqual(money.units, 100)
        self.assertEqual(money.nano, 500000000)
        self.assertAlmostEqual(float(money), 100.5, places=9)

    def test_init_invalid_type(self):
        """Тест инициализации с недопустимым типом"""
        with self.assertRaises(ValueError):
            Money("invalid")

    def test_to_float(self):
        """Тест конвертации в float"""
        money = Money(100.5)
        self.assertAlmostEqual(money.to_float(), 100.5, places=9)

    def test_to_quotation(self):
        """Тест конвертации в Quotation"""
        money = Money(100.5)
        quotation = money.to_quotation()
        self.assertEqual(quotation.units, 100)
        self.assertEqual(quotation.nano, 500000000)

    def test_to_money_value(self):
        """Тест конвертации в MoneyValue"""
        money = Money(100.5)
        money_value = money.to_money_value("rub")
        self.assertEqual(money_value.currency, "rub")
        self.assertEqual(money_value.units, 100)
        self.assertEqual(money_value.nano, 500000000)

    def test_addition(self):
        """Тест сложения"""
        money1 = Money(100.5)
        money2 = Money(50.25)
        result = money1 + money2
        self.assertAlmostEqual(float(result), 150.75, places=9)

    def test_addition_with_carry(self):
        """Тест сложения с переносом"""
        # Создаем Money с явным указанием nano для точного теста
        money1 = Money(100, nano=999999999)
        money2 = Money(0, nano=1)
        result = money1 + money2
        # Проверяем, что результат близок к 101.0
        self.assertAlmostEqual(float(result), 101.0, places=9)
        # Проверяем, что units увеличился на 1 (перенос из nano)
        self.assertEqual(result.units, 101)
        # Проверяем, что nano стал 0 после переноса
        self.assertEqual(result.nano, 0)

    def test_negation(self):
        """Тест отрицания"""
        money = Money(100.5)
        neg_money = -money
        self.assertEqual(neg_money.units, -100)
        self.assertEqual(neg_money.nano, -500000000)
        self.assertAlmostEqual(float(neg_money), -100.5, places=9)

    def test_subtraction(self):
        """Тест вычитания"""
        money1 = Money(100.5)
        money2 = Money(50.25)
        result = money1 - money2
        self.assertAlmostEqual(float(result), 50.25, places=9)

    def test_multiplication(self):
        """Тест умножения на int"""
        money = Money(100.5)
        result = money * 3
        self.assertAlmostEqual(float(result), 301.5, places=9)

    def test_multiplication_with_carry(self):
        """Тест умножения с переносом"""
        money = Money(100.999999999)
        result = money * 2
        # Проверяем, что результат близок к ожидаемому
        self.assertAlmostEqual(float(result), 201.999999998, places=8)

    def test_str_representation(self):
        """Тест строкового представления"""
        money = Money(100.5)
        str_repr = str(money)
        self.assertIn("Money", str_repr)
        self.assertIn("units=100", str_repr)
        self.assertIn("nano=500000000", str_repr)

    def test_comparison(self):
        """Тест сравнения"""
        money1 = Money(100.5)
        money2 = Money(100.5)
        money3 = Money(100.6)
        
        self.assertEqual(money1, money2)
        self.assertNotEqual(money1, money3)
        self.assertLess(money1, money3)
        self.assertGreater(money3, money1)

    def test_edge_cases(self):
        """Тест граничных случаев"""
        # Ноль
        zero = Money(0)
        self.assertEqual(zero.units, 0)
        self.assertEqual(zero.nano, 0)
        
        # Отрицательное число
        negative = Money(-100.5)
        self.assertEqual(negative.units, -101)  # math.floor(-100.5) = -101
        self.assertEqual(negative.nano, 500000000)  # -100.5 - (-101) = 0.5
        
        # Очень маленькое число
        small = Money(0.000000001)
        self.assertEqual(small.units, 0)
        self.assertEqual(small.nano, 1)

    def test_precision_limits(self):
        """Тест ограничений точности"""
        # Максимальная точность nano
        money = Money(0.999999999)
        self.assertEqual(money.nano, 999999999)
        
        # Проверка, что точность не теряется
        self.assertAlmostEqual(float(money), 0.999999999, places=9)


if __name__ == '__main__':
    unittest.main()
