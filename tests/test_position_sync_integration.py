"""
Тесты интеграции PositionSyncService с PositionRestorationService
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from robotlib.trading.position_sync_service import PositionSyncService
from robotlib.trading.position_restoration_service import PositionRestorationService
from robotlib.trading.position_restoration_interface import FIFOEntry, Position


class TestPositionSyncIntegration:
    """Тесты интеграции PositionSyncService"""
    
    @pytest.fixture
    def temp_db_path(self):
        """Временная база данных для тестов"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.fixture
    def mock_api_client(self):
        """Мок API клиента"""
        client = AsyncMock()
        client.get_portfolio = AsyncMock(return_value={
            'positions': [
                {
                    'figi': 'FUTIMOEXF000',
                    'quantity': 10.0,
                    'average_position_price': {'units': 2700, 'nano': 500000000},
                    'current_price': {'units': 2750, 'nano': 0},
                    'last_updated': datetime.now()
                }
            ]
        })
        client.get_operations_history = AsyncMock(return_value=[])
        return client
    
    @pytest.fixture
    def mock_restoration_service(self):
        """Мок сервиса восстановления"""
        service = AsyncMock()
        service.restore_fifo_from_api = AsyncMock(return_value={
            'FUTIMOEXF000': [
                FIFOEntry(
                    quantity=5,
                    price=2700.5,
                    timestamp=datetime.now(),
                    order_id='test_order_1',
                    direction='buy'
                ),
                FIFOEntry(
                    quantity=5,
                    price=2701.0,
                    timestamp=datetime.now(),
                    order_id='test_order_2',
                    direction='buy'
                )
            ]
        })
        return service
    
    @pytest.fixture
    def position_sync_service(self, temp_db_path, mock_api_client, mock_restoration_service):
        """Сервис синхронизации позиций"""
        return PositionSyncService(temp_db_path, mock_api_client, mock_restoration_service)
    
    @pytest.mark.asyncio
    async def test_sync_service_initialization(self, position_sync_service):
        """Тест инициализации сервиса синхронизации"""
        assert position_sync_service._db_path is not None
        assert position_sync_service._api_client is not None
        assert position_sync_service._restoration_service is not None
    
    @pytest.mark.asyncio
    async def test_sync_positions_calls_restoration_service(self, position_sync_service, mock_restoration_service):
        """Тест что синхронизация вызывает сервис восстановления"""
        # Инициализируем базу данных
        from robotlib.utils.sql_schema import init_db
        await init_db(position_sync_service._db_path)
        
        # Мокаем получение позиций из API чтобы вернуть позиции
        with patch.object(position_sync_service, '_get_positions_from_api', new_callable=AsyncMock) as mock_get_positions:
            mock_get_positions.return_value = {
                'FUTIMOEXF000': Position(
                    figi='FUTIMOEXF000',
                    quantity=10,
                    avg_price=2700.5,
                    last_updated=datetime.now()
                )
            }
            
            with patch.object(position_sync_service, '_restore_fifo_from_orders', new_callable=AsyncMock) as mock_restore_orders:
                mock_restore_orders.return_value = {}
                
                # Вызываем синхронизацию
                result = await position_sync_service.sync_positions_on_startup()
                
                # Проверяем что сервис восстановления был вызван
                mock_restoration_service.restore_fifo_from_api.assert_called_once()
                
                # Проверяем что результат содержит позиции
                assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_restoration_service_integration(self, temp_db_path, mock_api_client):
        """Тест интеграции с реальным сервисом восстановления"""
        # Создаем реальный сервис восстановления
        restoration_service = PositionRestorationService(mock_api_client, point_value=10.0)
        
        # Создаем сервис синхронизации
        sync_service = PositionSyncService(temp_db_path, mock_api_client, restoration_service)
        
        # Проверяем что сервис создался правильно
        assert sync_service._restoration_service is not None
        assert hasattr(sync_service._restoration_service, 'restore_fifo_from_api')
        assert hasattr(sync_service._restoration_service, 'validate_restored_fifo')
    
    @pytest.mark.asyncio
    async def test_restoration_service_point_value_caching(self, mock_api_client):
        """Тест кеширования point_value в сервисе восстановления"""
        restoration_service = PositionRestorationService(mock_api_client, point_value=15.0)
        
        # Проверяем что point_value кешируется
        assert restoration_service._point_value == 15.0
        
        # Проверяем что можно создать сервис синхронизации
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_path = f.name
        
        try:
            sync_service = PositionSyncService(temp_path, mock_api_client, restoration_service)
            assert sync_service._restoration_service._point_value == 15.0
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
