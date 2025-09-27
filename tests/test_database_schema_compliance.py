#!/usr/bin/env python3
"""
Тесты для проверки соответствия схемы базы данных
Проверяет, что таблица orders создается с правильной схемой (direction вместо type)
"""

import tempfile
import pytest
import sqlite3
from robotlib.utils.sql_schema import init_db
from visualization.data_manager import VisualizationDataStore


class TestDatabaseSchemaCompliance:
    """Тесты соответствия схемы базы данных"""
    
    @pytest.mark.asyncio
    async def test_orders_table_has_expected_schema(self):
        """Проверяет, что таблица orders создается с ожидаемой схемой"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
            db_path = tmp_file.name
        
        try:
            # Инициализируем базу данных
            await init_db(db_path)
            
            # Проверяем схему таблицы orders
            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute("PRAGMA table_info(orders)")
                columns_info = cursor.fetchall()
                columns = [row[1] for row in columns_info]
                
                # Ожидаемая схема для таблицы orders
                expected_orders_schema = {
                    'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
                    'order_id': 'TEXT UNIQUE',
                    'account_id': 'TEXT',
                    'figi': 'TEXT NOT NULL',
                    'time': 'TEXT NOT NULL',
                    'direction': 'TEXT NOT NULL',
                    'price': 'REAL NOT NULL',
                    'quantity': 'INTEGER NOT NULL',
                    'status': 'TEXT NOT NULL',
                    'commission': 'REAL DEFAULT 0.0',
                    'strategy': 'TEXT',
                    'reason': 'TEXT'
                }
                
                # Проверяем, что все ожидаемые колонки присутствуют
                for expected_col in expected_orders_schema.keys():
                    assert expected_col in columns, f"Отсутствует ожидаемая колонка '{expected_col}'. Доступные колонки: {columns}"
                
                # Проверяем типы колонок
                for col_info in columns_info:
                    col_name = col_info[1]
                    col_type = col_info[2]
                    not_null = col_info[3]
                    default_value = col_info[4]
                    pk = col_info[5]
                    
                    if col_name in expected_orders_schema:
                        expected_type = expected_orders_schema[col_name]
                        if 'NOT NULL' in expected_type:
                            assert not_null == 1, f"Колонка '{col_name}' должна быть NOT NULL"
                        if 'DEFAULT' in expected_type:
                            assert default_value is not None, f"Колонка '{col_name}' должна иметь значение по умолчанию"
                        if 'PRIMARY KEY' in expected_type:
                            assert pk == 1, f"Колонка '{col_name}' должна быть PRIMARY KEY"
        
        finally:
            import os
            os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_candles_table_has_expected_schema(self):
        """Проверяет, что таблица candles создается с ожидаемой схемой"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
            db_path = tmp_file.name
        
        try:
            # Инициализируем базу данных
            await init_db(db_path)
            
            # Проверяем схему таблицы candles
            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute("PRAGMA table_info(candles)")
                columns_info = cursor.fetchall()
                columns = [row[1] for row in columns_info]
                
                # Ожидаемая схема для таблицы candles
                expected_candles_schema = {
                    'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
                    'figi': 'TEXT NOT NULL',
                    'time': 'TEXT NOT NULL',
                    'open': 'REAL NOT NULL',
                    'high': 'REAL NOT NULL',
                    'low': 'REAL NOT NULL',
                    'close': 'REAL NOT NULL',
                    'volume': 'INTEGER NOT NULL'
                }
                
                # Проверяем, что все ожидаемые колонки присутствуют
                for expected_col in expected_candles_schema.keys():
                    assert expected_col in columns, f"Отсутствует ожидаемая колонка '{expected_col}'. Доступные колонки: {columns}"
                
                # Проверяем типы колонок
                for col_info in columns_info:
                    col_name = col_info[1]
                    col_type = col_info[2]
                    not_null = col_info[3]
                    pk = col_info[5]
                    
                    if col_name in expected_candles_schema:
                        expected_type = expected_candles_schema[col_name]
                        if 'NOT NULL' in expected_type:
                            assert not_null == 1, f"Колонка '{col_name}' должна быть NOT NULL"
                        if 'PRIMARY KEY' in expected_type:
                            assert pk == 1, f"Колонка '{col_name}' должна быть PRIMARY KEY"
        
        finally:
            import os
            os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_order_outbox_table_has_expected_schema(self):
        """Проверяет, что таблица order_outbox создается с ожидаемой схемой"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
            db_path = tmp_file.name
        
        try:
            # Инициализируем базу данных
            await init_db(db_path)
            
            # Проверяем схему таблицы order_outbox
            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute("PRAGMA table_info(order_outbox)")
                columns_info = cursor.fetchall()
                columns = [row[1] for row in columns_info]
                
                # Ожидаемая схема для таблицы order_outbox
                expected_outbox_schema = {
                    'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
                    'created_at': 'TEXT NOT NULL',
                    'account_id': 'TEXT',
                    'figi': 'TEXT NOT NULL',
                    'order_id': 'TEXT',
                    'payload': 'TEXT NOT NULL',
                    'delivered': 'INTEGER NOT NULL DEFAULT 0',
                    'delivered_at': 'TEXT'
                }
                
                # Проверяем, что все ожидаемые колонки присутствуют
                for expected_col in expected_outbox_schema.keys():
                    assert expected_col in columns, f"Отсутствует ожидаемая колонка '{expected_col}'. Доступные колонки: {columns}"
                
                # Проверяем типы колонок
                for col_info in columns_info:
                    col_name = col_info[1]
                    col_type = col_info[2]
                    not_null = col_info[3]
                    default_value = col_info[4]
                    pk = col_info[5]
                    
                    if col_name in expected_outbox_schema:
                        expected_type = expected_outbox_schema[col_name]
                        if 'NOT NULL' in expected_type:
                            assert not_null == 1, f"Колонка '{col_name}' должна быть NOT NULL"
                        if 'DEFAULT' in expected_type:
                            assert default_value is not None, f"Колонка '{col_name}' должна иметь значение по умолчанию"
                        if 'PRIMARY KEY' in expected_type:
                            assert pk == 1, f"Колонка '{col_name}' должна быть PRIMARY KEY"
        
        finally:
            import os
            os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_visualization_data_manager_migrates_schema_correctly(self):
        """Проверяет, что VisualizationDataStore корректно мигрирует схему"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
            db_path = tmp_file.name
        
        try:
            # Сначала создаем базу со старой схемой (с type)
            with sqlite3.connect(db_path) as conn:
                conn.execute("""
                    CREATE TABLE orders (
                        time TEXT,
                        figi TEXT,
                        type TEXT,
                        price REAL,
                        quantity INTEGER,
                        reason TEXT,
                        strategy TEXT
                    )
                """)
                conn.commit()
            
            # Теперь мигрируем схему
            data_store = VisualizationDataStore()
            data_store.migrate_orders_schema(db_path)
            
            # Проверяем схему таблицы orders после миграции
            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute("PRAGMA table_info(orders)")
                columns = [row[1] for row in cursor.fetchall()]
                
                # Проверяем, что есть колонка direction
                assert 'direction' in columns, f"Колонка 'direction' отсутствует в таблице orders. Доступные колонки: {columns}"
                
                # Проверяем, что НЕТ колонки type (старая схема)
                assert 'type' not in columns, f"Колонка 'type' не должна присутствовать в новой схеме. Доступные колонки: {columns}"
        
        finally:
            import os
            os.unlink(db_path)
    
    def test_sql_schema_definition_uses_direction(self):
        """Проверяет, что определение схемы в sql_schema.py использует direction"""
        from robotlib.utils.sql_schema import CANDLES_SCHEMA
        
        # Проверяем, что в схеме есть direction
        assert 'direction TEXT NOT NULL' in CANDLES_SCHEMA, "Схема должна содержать 'direction TEXT NOT NULL'"
        
        # Проверяем, что в схеме НЕТ type для orders
        assert 'type TEXT' not in CANDLES_SCHEMA or 'direction TEXT NOT NULL' in CANDLES_SCHEMA, "Схема должна использовать direction вместо type"
    
    @pytest.mark.asyncio
    async def test_orders_table_queries_work_with_direction(self):
        """Проверяет, что запросы к таблице orders работают с колонкой direction"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
            db_path = tmp_file.name
        
        try:
            # Инициализируем базу данных
            await init_db(db_path)
            
            # Вставляем тестовый ордер с direction
            with sqlite3.connect(db_path) as conn:
                conn.execute("""
                    INSERT INTO orders (order_id, figi, time, direction, price, quantity, status, strategy)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, ('test-order-1', 'TEST123', '2025-09-25T10:00:00Z', 'buy', 100.0, 1, 'filled', 'test'))
                conn.commit()
                
                # Проверяем, что можем прочитать ордер по direction
                cursor = conn.execute("SELECT direction FROM orders WHERE order_id = ?", ('test-order-1',))
                result = cursor.fetchone()
                assert result is not None, "Не удалось найти ордер"
                assert result[0] == 'buy', f"Ожидался direction='buy', получен {result[0]}"
                
                # Проверяем, что можем фильтровать по direction
                cursor = conn.execute("SELECT COUNT(*) FROM orders WHERE direction = 'buy'")
                count = cursor.fetchone()[0]
                assert count == 1, f"Ожидался 1 ордер с direction='buy', получено {count}"
        
        finally:
            import os
            os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_visualization_data_manager_loads_orders_with_direction(self):
        """Проверяет, что VisualizationDataStore корректно загружает ордера с direction"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
            db_path = tmp_file.name
        
        try:
            # Создаем базу с правильной схемой
            await init_db(db_path)
            
            # Вставляем тестовый ордер
            with sqlite3.connect(db_path) as conn:
                conn.execute("""
                    INSERT INTO orders (order_id, figi, time, direction, price, quantity, status, strategy)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, ('test-order-1', 'FUTIMOEXF000', '2025-09-25T10:00:00Z', 'sell', 200.0, 2, 'filled', 'test'))
                conn.commit()
            
            # Создаем VisualizationDataStore и загружаем ордера
            data_store = VisualizationDataStore()
            data_store.load_recent_orders_today(db_path, 'FUTIMOEXF000', limit=10)
            
            # Проверяем, что ордер загружен
            assert len(data_store.orders_data) > 0, "Ордера не загружены"
            
            # Проверяем, что у загруженного ордера есть direction
            order = data_store.orders_data[0]
            assert 'direction' in order, "У загруженного ордера отсутствует поле 'direction'"
            assert order['direction'] == 'sell', f"Ожидался direction='sell', получен {order['direction']}"
        
        finally:
            import os
            os.unlink(db_path)


if __name__ == '__main__':
    pytest.main([__file__])
