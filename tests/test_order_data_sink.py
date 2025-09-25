import pytest
import tempfile
import os
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from robotlib.ingestion.order_execution_sink import OrderExecutionSink
from robotlib.trading.order_types import OrderExecution, OrderIntent, OrderStatus, OrderDirection


class TestOrderExecutionSink:
    @pytest.fixture
    def temp_db_path(self):
        """Создает временный файл БД для тестов"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        yield db_path
        # Очистка после теста
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest.fixture
    def order_sink(self, temp_db_path):
        """Создает экземпляр OrderExecutionSink для тестов"""
        return OrderExecutionSink(
            db_path=temp_db_path,
            figi="TEST_FIGI"
        )

    @pytest.fixture
    def mock_order_execution(self):
        """Создает мок OrderExecution"""
        execution = Mock(spec=OrderExecution)
        execution.order_id = "test_order_123"
        execution.timestamp = datetime.now(timezone.utc)
        execution.price = 100.5
        execution.filled_quantity = 10
        execution.status = OrderStatus.FILLED
        execution.commission = 1.0
        execution.reason = "Test execution"
        return execution

    @pytest.fixture
    def mock_order_intent(self):
        """Создает мок OrderIntent"""
        intent = Mock(spec=OrderIntent)
        intent.figi = "TEST_FIGI"
        intent.quantity = 10
        intent.direction = OrderDirection.BUY
        intent.strategy = "test_strategy"
        return intent

    @pytest.mark.asyncio
    async def test_order_sink_initialization(self, temp_db_path):
        """Тест инициализации OrderExecutionSink"""
        sink = OrderExecutionSink(
            db_path=temp_db_path,
            figi="TEST_FIGI"
        )
        
        assert sink._db_path == temp_db_path
        assert sink._figi == "TEST_FIGI"

    @pytest.mark.asyncio
    async def test_on_order_execution_saves_to_db(self, order_sink, mock_order_execution, mock_order_intent):
        """Тест сохранения исполнения ордера в БД"""
        with patch('robotlib.ingestion.order_execution_sink.init_db', new_callable=AsyncMock) as mock_init_db, \
             patch('robotlib.ingestion.order_execution_sink.insert_orders', new_callable=AsyncMock) as mock_insert, \
             patch('robotlib.ingestion.order_execution_sink.outbox_enqueue_order', new_callable=AsyncMock) as mock_outbox:
            
            await order_sink.on_order_execution(mock_order_execution, mock_order_intent)
            
            mock_init_db.assert_called_once_with(order_sink._db_path)
            mock_insert.assert_called_once()
            mock_outbox.assert_called_once()
            
            # Проверяем аргументы insert_orders
            call_args = mock_insert.call_args[0]
            assert call_args[0] == order_sink._db_path
            assert len(call_args[1]) == 1
            
            order_record = call_args[1][0]
            assert order_record['order_id'] == "test_order_123"
            assert order_record['figi'] == "TEST_FIGI"
            assert order_record['type'] == "buy"
            assert order_record['price'] == 100.5
            assert order_record['quantity'] == 10
            assert order_record['status'] == "filled"
            assert order_record['strategy'] == "test_strategy"

    @pytest.mark.asyncio
    async def test_on_order_execution_sell_order(self, order_sink, mock_order_execution, mock_order_intent):
        """Тест сохранения ордера на продажу"""
        mock_order_intent.direction = OrderDirection.SELL
        
        with patch('robotlib.ingestion.order_execution_sink.init_db', new_callable=AsyncMock), \
             patch('robotlib.ingestion.order_execution_sink.insert_orders', new_callable=AsyncMock) as mock_insert, \
             patch('robotlib.ingestion.order_execution_sink.outbox_enqueue_order', new_callable=AsyncMock):
            
            await order_sink.on_order_execution(mock_order_execution, mock_order_intent)
            
            call_args = mock_insert.call_args[0]
            order_record = call_args[1][0]
            assert order_record['type'] == "sell"

    @pytest.mark.asyncio
    async def test_on_order_execution_handles_exception(self, order_sink, mock_order_execution, mock_order_intent):
        """Тест обработки исключений при сохранении ордера"""
        with patch('robotlib.ingestion.order_execution_sink.init_db', new_callable=AsyncMock) as mock_init_db:
            mock_init_db.side_effect = Exception("DB error")
            
            # Метод должен завершиться без исключения
            await order_sink.on_order_execution(mock_order_execution, mock_order_intent)

    @pytest.mark.asyncio
    async def test_on_order_execution_with_missing_attributes(self, order_sink):
        """Тест обработки OrderExecution с отсутствующими атрибутами"""
        execution = Mock(spec=OrderExecution)
        execution.order_id = "test_order_123"
        execution.timestamp = datetime.now(timezone.utc)
        execution.price = None  # Отсутствует цена
        execution.filled_quantity = None  # Отсутствует количество
        execution.status = OrderStatus.CANCELLED
        execution.commission = None
        execution.reason = None
        
        intent = Mock(spec=OrderIntent)
        intent.figi = "TEST_FIGI"
        intent.quantity = 10
        intent.direction = OrderDirection.BUY
        intent.strategy = None  # Отсутствует стратегия
        
        with patch('robotlib.ingestion.order_execution_sink.init_db', new_callable=AsyncMock), \
             patch('robotlib.ingestion.order_execution_sink.insert_orders', new_callable=AsyncMock) as mock_insert, \
             patch('robotlib.ingestion.order_execution_sink.outbox_enqueue_order', new_callable=AsyncMock):
            
            await order_sink.on_order_execution(execution, intent)
            
            call_args = mock_insert.call_args[0]
            order_record = call_args[1][0]
            
            assert order_record['price'] == 0.0  # Значение по умолчанию
            assert order_record['quantity'] == 10  # Из intent
            assert order_record['status'] == "cancelled"
            assert order_record['commission'] == 0.0
            assert order_record['strategy'] is None
            assert order_record['reason'] is None


    @pytest.mark.asyncio
    async def test_outbox_enqueue_on_success(self, order_sink, mock_order_execution, mock_order_intent):
        """Тест записи в outbox при успешном сохранении ордера"""
        with patch('robotlib.ingestion.order_execution_sink.init_db', new_callable=AsyncMock), \
             patch('robotlib.ingestion.order_execution_sink.insert_orders', new_callable=AsyncMock), \
             patch('robotlib.ingestion.order_execution_sink.outbox_enqueue_order', new_callable=AsyncMock) as mock_outbox:
            
            await order_sink.on_order_execution(mock_order_execution, mock_order_intent)
            
            mock_outbox.assert_called_once()
            call_args = mock_outbox.call_args[1]  # keyword arguments
            assert call_args['figi'] == "TEST_FIGI"
            assert call_args['order_id'] == "test_order_123"

    @pytest.mark.asyncio
    async def test_outbox_enqueue_handles_exception(self, order_sink, mock_order_execution, mock_order_intent):
        """Тест обработки исключений при записи в outbox"""
        with patch('robotlib.ingestion.order_execution_sink.init_db', new_callable=AsyncMock), \
             patch('robotlib.ingestion.order_execution_sink.insert_orders', new_callable=AsyncMock), \
             patch('robotlib.ingestion.order_execution_sink.outbox_enqueue_order', new_callable=AsyncMock) as mock_outbox:
            
            mock_outbox.side_effect = Exception("Outbox error")
            
            # Метод должен завершиться без исключения
            await order_sink.on_order_execution(mock_order_execution, mock_order_intent)
            
            mock_outbox.assert_called_once()

    @pytest.mark.asyncio
    async def test_logging_on_successful_save(self, order_sink, mock_order_execution, mock_order_intent):
        """Тест логирования при успешном сохранении"""
        with patch('robotlib.ingestion.order_execution_sink.init_db', new_callable=AsyncMock), \
             patch('robotlib.ingestion.order_execution_sink.insert_orders', new_callable=AsyncMock), \
             patch('robotlib.ingestion.order_execution_sink.outbox_enqueue_order', new_callable=AsyncMock), \
             patch.object(order_sink._logger, 'info') as mock_log_info:
            
            await order_sink.on_order_execution(mock_order_execution, mock_order_intent)
            
            mock_log_info.assert_called_once()
            log_message = mock_log_info.call_args[0][0]
            assert "Ордер записан в БД" in log_message
            assert "test_order_123" in log_message

    @pytest.mark.asyncio
    async def test_logging_handles_exception(self, order_sink, mock_order_execution, mock_order_intent):
        """Тест обработки исключений при логировании"""
        with patch('robotlib.ingestion.order_execution_sink.init_db', new_callable=AsyncMock), \
             patch('robotlib.ingestion.order_execution_sink.insert_orders', new_callable=AsyncMock), \
             patch('robotlib.ingestion.order_execution_sink.outbox_enqueue_order', new_callable=AsyncMock), \
             patch.object(order_sink._logger, 'info', side_effect=Exception("Log error")):
            
            # Метод должен завершиться без исключения
            await order_sink.on_order_execution(mock_order_execution, mock_order_intent)
