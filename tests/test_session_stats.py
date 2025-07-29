"""
Тесты для SessionStats
"""
import unittest
from datetime import datetime
from robotlib.trading.session_stats import SessionStats


class TestSessionStats(unittest.TestCase):
    """Тесты для класса SessionStats"""
    
    def setUp(self):
        """Настройка тестов"""
        self.stats = SessionStats()
    
    def test_initial_values(self):
        """Тест начальных значений"""
        self.assertEqual(self.stats.total_signals, 0)
        self.assertEqual(self.stats.successful_orders, 0)
        self.assertEqual(self.stats.failed_orders, 0)
        self.assertEqual(self.stats.total_volume, 0.0)
        self.assertEqual(self.stats.total_profit, 0.0)
        self.assertIsNotNone(self.stats.start_time)
        self.assertIsNone(self.stats.end_time)
    
    def test_add_signal(self):
        """Тест добавления сигнала"""
        self.stats.add_signal()
        self.assertEqual(self.stats.total_signals, 1)
        
        self.stats.add_signal()
        self.stats.add_signal()
        self.assertEqual(self.stats.total_signals, 3)
    
    def test_add_successful_order(self):
        """Тест добавления успешного ордера"""
        self.stats.add_successful_order(volume=100.0, profit=10.0)
        self.assertEqual(self.stats.successful_orders, 1)
        self.assertEqual(self.stats.total_volume, 100.0)
        self.assertEqual(self.stats.total_profit, 10.0)
        
        self.stats.add_successful_order(volume=50.0, profit=5.0)
        self.assertEqual(self.stats.successful_orders, 2)
        self.assertEqual(self.stats.total_volume, 150.0)
        self.assertEqual(self.stats.total_profit, 15.0)
    
    def test_add_failed_order(self):
        """Тест добавления неудачного ордера"""
        self.stats.add_failed_order()
        self.assertEqual(self.stats.failed_orders, 1)
        
        self.stats.add_failed_order()
        self.assertEqual(self.stats.failed_orders, 2)
    
    def test_update_balance(self):
        """Тест обновления баланса"""
        # Начальный баланс
        self.stats.update_balance(1000.0)
        self.assertEqual(self.stats.current_balance, 1000.0)
        self.assertEqual(self.stats.peak_balance, 1000.0)
        self.assertEqual(self.stats.current_drawdown, 0.0)
        
        # Увеличение баланса
        self.stats.update_balance(1200.0)
        self.assertEqual(self.stats.current_balance, 1200.0)
        self.assertEqual(self.stats.peak_balance, 1200.0)
        self.assertEqual(self.stats.current_drawdown, 0.0)
        
        # Уменьшение баланса (просадка)
        self.stats.update_balance(1100.0)
        self.assertEqual(self.stats.current_balance, 1100.0)
        self.assertEqual(self.stats.peak_balance, 1200.0)
        self.assertEqual(self.stats.current_drawdown, 100.0)
        self.assertEqual(self.stats.max_drawdown, 100.0)
        
        # Еще больше просадка
        self.stats.update_balance(1000.0)
        self.assertEqual(self.stats.current_drawdown, 200.0)
        self.assertEqual(self.stats.max_drawdown, 200.0)
    
    def test_get_stats_dict(self):
        """Тест получения статистики в виде словаря"""
        self.stats.add_signal()
        self.stats.add_successful_order(100.0, 10.0)
        self.stats.add_failed_order()
        self.stats.update_balance(1000.0)
        
        stats_dict = self.stats.get_stats_dict()
        
        self.assertIn('start_time', stats_dict)
        self.assertIn('end_time', stats_dict)
        self.assertIn('duration_seconds', stats_dict)
        self.assertEqual(stats_dict['total_signals'], 1)
        self.assertEqual(stats_dict['successful_orders'], 1)
        self.assertEqual(stats_dict['failed_orders'], 1)
        self.assertEqual(stats_dict['success_rate'], 0.5)
        self.assertEqual(stats_dict['total_volume'], 100.0)
        self.assertEqual(stats_dict['total_profit'], 10.0)
        self.assertEqual(stats_dict['current_balance'], 1000.0)
    
    def test_finish_session(self):
        """Тест завершения сессии"""
        self.stats.finish_session()
        self.assertIsNotNone(self.stats.end_time)
        self.assertIsInstance(self.stats.end_time, datetime)
    
    def test_success_rate_calculation(self):
        """Тест расчета процента успеха"""
        # Нет ордеров
        stats_dict = self.stats.get_stats_dict()
        self.assertEqual(stats_dict['success_rate'], 0.0)
        
        # Только успешные
        self.stats.add_successful_order(100.0, 10.0)
        stats_dict = self.stats.get_stats_dict()
        self.assertEqual(stats_dict['success_rate'], 1.0)
        
        # Смешанные результаты
        self.stats.add_failed_order()
        stats_dict = self.stats.get_stats_dict()
        self.assertEqual(stats_dict['success_rate'], 0.5)


if __name__ == '__main__':
    unittest.main()
