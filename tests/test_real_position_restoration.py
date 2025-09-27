"""
Тесты реального восстановления позиций из API
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from tinkoff.invest.schemas import MoneyValue

from robotlib.trading.position_restoration_service import PositionRestorationService
from robotlib.trading.position_restoration_interface import FIFOEntry, Position


class TestRealPositionRestoration:
    """Тесты реального восстановления позиций"""
    
    @pytest.fixture
    def mock_api_client(self):
        """Мок API клиента с реальными данными"""
        client = AsyncMock()
        
        # Мокаем историю операций - возвращаем объект с атрибутом operations
        operations_list = [
            Mock(
                id="op_1",
                figi="FUTIMOEXF000",
                quantity=5,
                date=datetime.now() - timedelta(days=1),
                price=MoneyValue(units=2700, nano=500000000),  # 2700.5
                operation_type=15  # OPERATION_TYPE_BUY
            ),
            Mock(
                id="op_2", 
                figi="FUTIMOEXF000",
                quantity=3,
                date=datetime.now() - timedelta(hours=12),
                price=MoneyValue(units=2701, nano=0),  # 2701.0
                operation_type=15  # OPERATION_TYPE_BUY
            ),
            Mock(
                id="op_3",
                figi="FUTIMOEXF000", 
                quantity=2,
                date=datetime.now() - timedelta(hours=6),
                price=MoneyValue(units=2705, nano=0),  # 2705.0
                operation_type=22  # OPERATION_TYPE_SELL
            )
        ]
        
        # Создаем Mock объект с атрибутом operations
        operations_response = Mock()
        operations_response.operations = operations_list
        client.get_operations_history = AsyncMock(return_value=operations_response)
        
        return client
    
    @pytest.fixture
    def restoration_service(self, mock_api_client):
        """Сервис восстановления с реальными данными"""
        return PositionRestorationService(mock_api_client, point_value=10.0)
    
    @pytest.mark.asyncio
    async def test_real_fifo_restoration(self, restoration_service):
        """Тест реального восстановления FIFO из операций"""
        # Вызываем реальный метод восстановления
        api_positions = {
            'FUTIMOEXF000': Position(
                figi='FUTIMOEXF000',
                quantity=6,  # 5 + 3 - 2 = 6
                avg_price=2700.8,
                last_updated=datetime.now()
            )
        }
        
        existing_fifo = {}
        
        # Восстанавливаем FIFO
        result = await restoration_service.restore_fifo_from_api(api_positions, existing_fifo)
        
        # Проверяем результат
        assert 'FUTIMOEXF000' in result
        fifo_entries = result['FUTIMOEXF000']
        
        # Должно быть 3 записи (2 покупки + 1 продажа)
        assert len(fifo_entries) == 3
        
        # Проверяем первую запись (покупка 5 лотов по 2700.5)
        first_entry = fifo_entries[0]
        assert first_entry.quantity == 5
        assert first_entry.price == 2700.5 * 10.0  # point_value = 10.0
        assert first_entry.direction == "buy"
        assert first_entry.order_id == "op_1"
        
        # Проверяем вторую запись (покупка 3 лота по 2701.0)
        second_entry = fifo_entries[1]
        assert second_entry.quantity == 3
        assert second_entry.price == 2701.0 * 10.0
        assert second_entry.direction == "buy"
        assert second_entry.order_id == "op_2"
        
        # Проверяем третью запись (продажа 2 лотов по 2705.0)
        third_entry = fifo_entries[2]
        assert third_entry.quantity == 2
        assert third_entry.price == 2705.0 * 10.0
        assert third_entry.direction == "sell"
        assert third_entry.order_id == "op_3"
    
    @pytest.mark.asyncio
    async def test_price_extraction_with_point_value(self, restoration_service):
        """Тест извлечения цены с учетом point_value"""
        # Создаем мок операции
        operation = Mock()
        operation.id = "test_op"
        operation.price = MoneyValue(units=2700, nano=500000000)  # 2700.5
        operation.quantity = 5
        operation.date = datetime.now()
        operation.operation_type = 15  # OPERATION_TYPE_BUY
        
        # Извлекаем цену
        price = await restoration_service._extract_price_from_operation(operation)
        
        # Цена должна быть умножена на point_value (10.0)
        expected_price = 2700.5 * 10.0  # 27005.0
        assert price == expected_price
    
    @pytest.mark.asyncio
    async def test_direction_determination(self, restoration_service):
        """Тест определения направления операции"""
        # Тест покупки
        buy_operation = Mock()
        buy_operation.quantity = 5
        buy_operation.operation_type = 15  # OPERATION_TYPE_BUY
        
        direction = restoration_service._determine_operation_direction(buy_operation)
        assert direction == "buy"
        
        # Тест продажи
        sell_operation = Mock()
        sell_operation.quantity = -3
        sell_operation.operation_type = 22  # OPERATION_TYPE_SELL
        
        direction = restoration_service._determine_operation_direction(sell_operation)
        assert direction == "sell"
    
    @pytest.mark.asyncio
    async def test_fifo_entry_creation(self, restoration_service):
        """Тест создания FIFO записи из операции"""
        # Создаем мок операции
        operation = Mock()
        operation.id = "test_order_123"
        operation.quantity = 5
        operation.date = datetime.now() - timedelta(hours=1)
        operation.price = MoneyValue(units=2700, nano=500000000)
        operation.operation_type = 15  # OPERATION_TYPE_BUY
        
        # Создаем FIFO запись
        fifo_entry = await restoration_service._create_fifo_entry_from_operation(operation)
        
        # Проверяем результат
        assert fifo_entry is not None
        assert fifo_entry.quantity == 5
        assert fifo_entry.price == 2700.5 * 10.0  # point_value = 10.0
        assert fifo_entry.direction == "buy"
        assert fifo_entry.order_id == "test_order_123"
        assert fifo_entry.timestamp == operation.date
    
    @pytest.mark.asyncio
    async def test_validation_of_restored_fifo(self, restoration_service):
        """Тест валидации восстановленных FIFO данных"""
        # Создаем тестовые FIFO данные
        fifo_data = {
            'FUTIMOEXF000': [
                FIFOEntry(
                    quantity=5,
                    price=27005.0,  # 2700.5 * 10.0
                    timestamp=datetime.now() - timedelta(days=1),
                    order_id="op_1",
                    direction="buy"
                ),
                FIFOEntry(
                    quantity=3,
                    price=27010.0,  # 2701.0 * 10.0
                    timestamp=datetime.now() - timedelta(hours=12),
                    order_id="op_2", 
                    direction="buy"
                )
            ]
        }
        
        # Валидируем данные
        validation_results = await restoration_service.validate_restored_fifo(fifo_data)
        
        # Проверяем результат валидации
        assert 'FUTIMOEXF000' in validation_results
        assert validation_results['FUTIMOEXF000'] == True  # Данные валидны
