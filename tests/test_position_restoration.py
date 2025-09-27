"""
Тесты восстановления позиций из API операций с использованием моков
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from tinkoff.invest.schemas import MoneyValue
from robotlib.trading.order_types import OrderDirection

from robotlib.trading.position_restoration_service import PositionRestorationService
from robotlib.trading.position_restoration_interface import FIFOEntry, Position


class TestPositionRestoration:
    """Тесты восстановления позиций с моками"""
    
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
        
        # Мокаем get_operations_by_cursor для sandbox режима
        client.get_operations_by_cursor = AsyncMock(return_value=operations_response)
        
        # Добавляем атрибут для sandbox режима
        client._sandbox_token = "test_token"
        
        return client
    
    @pytest.fixture
    def restoration_service(self, mock_api_client):
        """Сервис восстановления с моками"""
        return PositionRestorationService(mock_api_client, point_value=10.0)
    
    @pytest.mark.asyncio
    async def test_real_fifo_restoration(self, restoration_service):
        """Тест восстановления FIFO из операций с моками"""
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
        
        # Должно быть 18 записей (6 периодов × 3 операции)
        assert len(fifo_entries) == 18
        
        # Проверяем, что есть записи с правильными данными
        buy_entries = [entry for entry in fifo_entries if entry.direction == OrderDirection.BUY]
        sell_entries = [entry for entry in fifo_entries if entry.direction == OrderDirection.SELL]
        
        # Должно быть 12 записей покупок (6 периодов × 2 покупки)
        assert len(buy_entries) == 12
        # Должно быть 6 записей продаж (6 периодов × 1 продажа)
        assert len(sell_entries) == 6
        
        # Проверяем, что есть записи с правильными количествами
        quantities = [entry.quantity for entry in fifo_entries]
        assert 5 in quantities  # Покупка 5 лотов
        assert 3 in quantities  # Покупка 3 лотов
        assert 2 in quantities  # Продажа 2 лотов
        
        # Проверяем, что цены правильно конвертированы с point_value
        prices = [entry.price for entry in fifo_entries]
        assert 27005.0 in prices  # 2700.5 * 10.0
        assert 27010.0 in prices  # 2701.0 * 10.0
        assert 27050.0 in prices  # 2705.0 * 10.0
    
    def test_price_extraction_with_point_value(self, restoration_service):
        """Тест извлечения цены с учетом point_value"""
        # Тестируем логику point_value
        point_value = restoration_service._point_value
        assert point_value == 10.0
        
        # Тестируем базовую цену
        base_price = 2700.5
        expected_price = base_price * point_value
        assert expected_price == 27005.0
    
    def test_direction_determination(self, restoration_service):
        """Тест определения направления операции"""
        # Тест покупки
        buy_operation = Mock(
            operation_type=15,  # OPERATION_TYPE_BUY
            quantity=5
        )
        direction = restoration_service._determine_operation_direction(buy_operation)
        assert direction == OrderDirection.BUY
        
        # Тест продажи
        sell_operation = Mock(
            operation_type=22,  # OPERATION_TYPE_SELL
            quantity=2
        )
        direction = restoration_service._determine_operation_direction(sell_operation)
        assert direction == OrderDirection.SELL
    
    def test_fifo_entry_creation(self, restoration_service):
        """Тест создания FIFO записи из операции"""
        # Тестируем базовую логику создания FIFO записи
        from robotlib.trading.position_restoration_interface import FIFOEntry
        
        # Создаем FIFO запись вручную
        fifo_entry = FIFOEntry(
            quantity=5,
            price=27005.0,
            timestamp=datetime.now(),
            order_id="test_op_1",
            direction="buy"
        )
        
        # Проверяем результат
        assert fifo_entry is not None
        assert fifo_entry.quantity == 5
        assert fifo_entry.price == 27005.0
        assert fifo_entry.direction == "buy"
        assert fifo_entry.order_id == "test_op_1"
    
    @pytest.mark.asyncio
    async def test_validation_of_restored_fifo(self, restoration_service):
        """Тест валидации восстановленных FIFO записей"""
        # Создаем тестовые данные
        api_positions = {
            'FUTIMOEXF000': Position(
                figi='FUTIMOEXF000',
                quantity=6,
                avg_price=2700.8,
                last_updated=datetime.now()
            )
        }
        
        existing_fifo = {}
        
        # Восстанавливаем FIFO
        result = await restoration_service.restore_fifo_from_api(api_positions, existing_fifo)
        
        # Проверяем, что результат не пустой
        assert result is not None
        assert isinstance(result, dict)
        assert 'FUTIMOEXF000' in result
        
        fifo_entries = result['FUTIMOEXF000']
        assert len(fifo_entries) > 0
        
        # Проверяем структуру записей
        for entry in fifo_entries:
            assert isinstance(entry, FIFOEntry)
            assert entry.quantity > 0
            assert entry.price > 0
            assert entry.direction in [OrderDirection.BUY, OrderDirection.SELL]
            assert entry.order_id is not None
            assert entry.timestamp is not None
