#!/usr/bin/env python3
"""
Тесты для конфигурации системы
"""
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from dataclasses import dataclass
from config_data.config import TCSClient, Config, load_config


class TestTCSClient(unittest.TestCase):
    """Тесты для класса TCSClient"""
    
    def test_tcs_client_creation_with_defaults(self):
        """Тест создания TCSClient с значениями по умолчанию"""
        client = TCSClient(
            token="test_token",
            account_id="test_account",
            sandbox_token="test_sandbox"
        )
        
        self.assertEqual(client.token, "test_token")
        self.assertEqual(client.account_id, "test_account")
        self.assertEqual(client.sandbox_token, "test_sandbox")
        self.assertEqual(client.rate_limit_get_rps, 8.0)
        self.assertEqual(client.rate_limit_get_burst, 16)
        self.assertEqual(client.rate_limit_post_rps, 2.0)
        self.assertEqual(client.rate_limit_post_burst, 4)
    
    def test_tcs_client_creation_with_custom_limits(self):
        """Тест создания TCSClient с кастомными лимитами"""
        client = TCSClient(
            token="test_token",
            account_id="test_account",
            sandbox_token="test_sandbox",
            rate_limit_get_rps=10.0,
            rate_limit_get_burst=20,
            rate_limit_post_rps=3.0,
            rate_limit_post_burst=6
        )
        
        self.assertEqual(client.rate_limit_get_rps, 10.0)
        self.assertEqual(client.rate_limit_get_burst, 20)
        self.assertEqual(client.rate_limit_post_rps, 3.0)
        self.assertEqual(client.rate_limit_post_burst, 6)


class TestConfig(unittest.TestCase):
    """Тесты для класса Config"""
    
    def test_config_creation_with_defaults(self):
        """Тест создания Config с значениями по умолчанию"""
        tcs_client = TCSClient(
            token="test_token",
            account_id="test_account",
            sandbox_token="test_sandbox"
        )
        
        config = Config(
            tcs_client=tcs_client,
            clearing_day_start="14:00",
            clearing_day_end="14:05",
            clearing_evening_start="18:50",
            clearing_evening_end="19:05"
        )
        
        self.assertEqual(config.tcs_client, tcs_client)
        self.assertEqual(config.clearing_day_start, "14:00")
        self.assertEqual(config.clearing_day_end, "14:05")
        self.assertEqual(config.clearing_evening_start, "18:50")
        self.assertEqual(config.clearing_evening_end, "19:05")
        self.assertTrue(config.watchdog_enabled)
        self.assertEqual(config.watchdog_stale_seconds, 120)
        self.assertTrue(config.watchdog_require_open_market)
    
    def test_config_creation_with_custom_watchdog(self):
        """Тест создания Config с кастомными настройками watchdog"""
        tcs_client = TCSClient(
            token="test_token",
            account_id="test_account",
            sandbox_token="test_sandbox"
        )
        
        config = Config(
            tcs_client=tcs_client,
            clearing_day_start="14:00",
            clearing_day_end="14:05",
            clearing_evening_start="18:50",
            clearing_evening_end="19:05",
            watchdog_enabled=False,
            watchdog_stale_seconds=300,
            watchdog_require_open_market=False
        )
        
        self.assertFalse(config.watchdog_enabled)
        self.assertEqual(config.watchdog_stale_seconds, 300)
        self.assertFalse(config.watchdog_require_open_market)


class TestLoadConfig(unittest.TestCase):
    """Тесты для функции load_config"""
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        self.test_env_content = """
TINKOFF_TOKEN=test_token_123
TINKOFF_ACCOUNT=test_account_456
SANDBOX_TOKEN=test_sandbox_789
TCS_RATE_GET_RPS=10.0
TCS_RATE_GET_BURST=20
TCS_RATE_POST_RPS=3.0
TCS_RATE_POST_BURST=6
CLEARING_DAY_START=15:00
CLEARING_DAY_END=15:05
CLEARING_EVENING_START=19:00
CLEARING_EVENING_END=19:05
WATCHDOG_ENABLED=false
WATCHDOG_STALE_SECONDS=300
WATCHDOG_REQUIRE_OPEN_MARKET=false
"""
    
    def test_load_config_from_file(self):
        """Тест загрузки конфигурации из файла"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write(self.test_env_content)
            f.flush()
            
            try:
                # Очищаем переменные окружения для чистого теста
                with patch.dict(os.environ, {}, clear=True):
                    config = load_config(f.name)
                    
                    # Проверяем TCSClient
                    self.assertEqual(config.tcs_client.token, "test_token_123")
                    self.assertEqual(config.tcs_client.account_id, "test_account_456")
                    self.assertEqual(config.tcs_client.sandbox_token, "test_sandbox_789")
                    self.assertEqual(config.tcs_client.rate_limit_get_rps, 10.0)
                    self.assertEqual(config.tcs_client.rate_limit_get_burst, 20)
                    self.assertEqual(config.tcs_client.rate_limit_post_rps, 3.0)
                    self.assertEqual(config.tcs_client.rate_limit_post_burst, 6)
                    
                    # Проверяем Config
                    self.assertEqual(config.clearing_day_start, "15:00")
                    self.assertEqual(config.clearing_day_end, "15:05")
                    self.assertEqual(config.clearing_evening_start, "19:00")
                    self.assertEqual(config.clearing_evening_end, "19:05")
                    self.assertFalse(config.watchdog_enabled)
                    self.assertEqual(config.watchdog_stale_seconds, 300)
                    self.assertFalse(config.watchdog_require_open_market)
                
            finally:
                os.unlink(f.name)
    
    def test_load_config_with_defaults(self):
        """Тест загрузки конфигурации с значениями по умолчанию"""
        minimal_env_content = """
TINKOFF_TOKEN=test_token
TINKOFF_ACCOUNT=test_account
SANDBOX_TOKEN=test_sandbox
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write(minimal_env_content)
            f.flush()
            
            try:
                # Очищаем переменные окружения для чистого теста
                with patch.dict(os.environ, {}, clear=True):
                    config = load_config(f.name)
                    
                    # Проверяем значения по умолчанию
                    self.assertEqual(config.tcs_client.rate_limit_get_rps, 8.0)
                    self.assertEqual(config.tcs_client.rate_limit_get_burst, 16)
                    self.assertEqual(config.tcs_client.rate_limit_post_rps, 2.0)
                    self.assertEqual(config.tcs_client.rate_limit_post_burst, 4)
                    
                    self.assertEqual(config.clearing_day_start, "14:00")
                    self.assertEqual(config.clearing_day_end, "14:05")
                    self.assertEqual(config.clearing_evening_start, "18:50")
                    self.assertEqual(config.clearing_evening_end, "19:05")
                    
                    self.assertTrue(config.watchdog_enabled)
                    self.assertEqual(config.watchdog_stale_seconds, 120)
                    self.assertTrue(config.watchdog_require_open_market)
                
            finally:
                os.unlink(f.name)
    
    def test_load_config_without_file(self):
        """Тест загрузки конфигурации без файла (использует переменные окружения)"""
        with patch.dict(os.environ, {
            'TINKOFF_TOKEN': 'env_token',
            'TINKOFF_ACCOUNT': 'env_account',
            'SANDBOX_TOKEN': 'env_sandbox',
            'TCS_RATE_GET_RPS': '12.0',
            'WATCHDOG_ENABLED': 'false'
        }):
            config = load_config()
            
            self.assertEqual(config.tcs_client.token, "env_token")
            self.assertEqual(config.tcs_client.account_id, "env_account")
            self.assertEqual(config.tcs_client.sandbox_token, "env_sandbox")
            self.assertEqual(config.tcs_client.rate_limit_get_rps, 12.0)
            self.assertFalse(config.watchdog_enabled)
    
    def test_load_config_missing_required_vars(self):
        """Тест загрузки конфигурации с отсутствующими обязательными переменными"""
        with patch.dict(os.environ, {}, clear=True):
            # Создаем пустой .env файл
            with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
                f.write("")
                f.flush()
                
                try:
                    with self.assertRaises(Exception):
                        load_config(f.name)
                finally:
                    os.unlink(f.name)
    
    def test_load_config_invalid_types(self):
        """Тест загрузки конфигурации с неверными типами данных"""
        invalid_env_content = """
TINKOFF_TOKEN=test_token
TINKOFF_ACCOUNT=test_account
SANDBOX_TOKEN=test_sandbox
TCS_RATE_GET_RPS=invalid_float
WATCHDOG_STALE_SECONDS=invalid_int
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write(invalid_env_content)
            f.flush()
            
            try:
                with patch.dict(os.environ, {}, clear=True):
                    with self.assertRaises(ValueError):
                        load_config(f.name)
            finally:
                os.unlink(f.name)
    
    def test_load_config_boolean_values(self):
        """Тест загрузки конфигурации с различными boolean значениями"""
        boolean_test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("0", False),
        ]
        
        for bool_value, expected in boolean_test_cases:
            with self.subTest(bool_value=bool_value):
                env_content = f"""
TINKOFF_TOKEN=test_token
TINKOFF_ACCOUNT=test_account
SANDBOX_TOKEN=test_sandbox
WATCHDOG_ENABLED={bool_value}
WATCHDOG_REQUIRE_OPEN_MARKET={bool_value}
"""
                
                with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
                    f.write(env_content)
                    f.flush()
                    
                    try:
                        with patch.dict(os.environ, {}, clear=True):
                            config = load_config(f.name)
                            self.assertEqual(config.watchdog_enabled, expected)
                            self.assertEqual(config.watchdog_require_open_market, expected)
                    finally:
                        os.unlink(f.name)


if __name__ == '__main__':
    unittest.main()
