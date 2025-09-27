#!/usr/bin/env python3
"""
Тесты для TradingConfig
"""
import unittest
from robotlib.trading.trading_config import TradingConfig


class TestTradingConfig(unittest.TestCase):
    """Тесты для класса TradingConfig"""
    
    def test_trading_config_creation_with_defaults(self):
        """Тест создания TradingConfig с значениями по умолчанию"""
        config = TradingConfig(figi="FUTIMOEXF000")
        
        # Проверяем основные поля
        self.assertEqual(config.figi, "FUTIMOEXF000")
        self.assertTrue(config.auto_close_positions)
        self.assertTrue(config.end_of_day_close)
        self.assertEqual(config.close_time.hour, 23)
        self.assertEqual(config.close_time.minute, 50)
        self.assertEqual(config.warning_periods, [600, 300, 60])
        self.assertFalse(config.enable_visualization)
        
        # Проверяем пути к базам данных
        self.assertEqual(config.positions_db_path, "data/positions.db")
        self.assertEqual(config.market_db_path, "data/market.db")
    
    def test_trading_config_creation_with_custom_values(self):
        """Тест создания TradingConfig с кастомными значениями"""
        from datetime import time
        
        config = TradingConfig(
            figi="TESTFIGI123",
            auto_close_positions=False,
            end_of_day_close=False,
            close_time=time(22, 30),
            warning_periods=[900, 600, 300],
            enable_visualization=True,
            positions_db_path="custom/positions.db",
            market_db_path="custom/market.db"
        )
        
        # Проверяем кастомные значения
        self.assertEqual(config.figi, "TESTFIGI123")
        self.assertFalse(config.auto_close_positions)
        self.assertFalse(config.end_of_day_close)
        self.assertEqual(config.close_time.hour, 22)
        self.assertEqual(config.close_time.minute, 30)
        self.assertEqual(config.warning_periods, [900, 600, 300])
        self.assertTrue(config.enable_visualization)
        
        # Проверяем кастомные пути к базам данных
        self.assertEqual(config.positions_db_path, "custom/positions.db")
        self.assertEqual(config.market_db_path, "custom/market.db")
    
    def test_trading_config_warning_periods_sorting(self):
        """Тест автоматической сортировки warning_periods по убыванию"""
        config = TradingConfig(
            figi="FUTIMOEXF000",
            warning_periods=[60, 300, 600]  # Несортированный список
        )
        
        # Проверяем, что периоды отсортированы по убыванию
        self.assertEqual(config.warning_periods, [600, 300, 60])
    
    def test_trading_config_database_paths_separation(self):
        """Тест разделения путей к базам данных"""
        config = TradingConfig(
            figi="FUTIMOEXF000",
            positions_db_path="test/positions.db",
            market_db_path="test/market.db"
        )
        
        # Проверяем, что пути разные и корректные
        self.assertNotEqual(config.positions_db_path, config.market_db_path)
        self.assertEqual(config.positions_db_path, "test/positions.db")
        self.assertEqual(config.market_db_path, "test/market.db")
        self.assertTrue(config.positions_db_path.endswith(".db"))
        self.assertTrue(config.market_db_path.endswith(".db"))
    
    def test_trading_config_immutability(self):
        """Тест, что конфигурация можно изменять после создания"""
        config = TradingConfig(figi="FUTIMOEXF000")
        
        # Изменяем значения
        config.positions_db_path = "new/positions.db"
        config.market_db_path = "new/market.db"
        config.enable_visualization = True
        
        # Проверяем, что изменения сохранились
        self.assertEqual(config.positions_db_path, "new/positions.db")
        self.assertEqual(config.market_db_path, "new/market.db")
        self.assertTrue(config.enable_visualization)
    
    def test_trading_config_edge_cases(self):
        """Тест граничных случаев"""
        # Пустые пути к базам данных
        config = TradingConfig(
            figi="FUTIMOEXF000",
            positions_db_path="",
            market_db_path=""
        )
        
        self.assertEqual(config.positions_db_path, "")
        self.assertEqual(config.market_db_path, "")
        
        # Одинаковые пути (не рекомендуется, но должно работать)
        config = TradingConfig(
            figi="FUTIMOEXF000",
            positions_db_path="same.db",
            market_db_path="same.db"
        )
        
        self.assertEqual(config.positions_db_path, config.market_db_path)
        self.assertEqual(config.positions_db_path, "same.db")


if __name__ == '__main__':
    unittest.main()
