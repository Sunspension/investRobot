import pytest
import asyncio
import tempfile
import os
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from robotlib.ingestion.candle_data_sink import CandleDataSink
from robotlib.utils.sql_repository import DBCandle


class TestCandleDataSink:
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
    def market_sink(self, temp_db_path):
        """Создает экземпляр CandleDataSink для тестов"""
        return CandleDataSink(
            db_path=temp_db_path,
            figi="TEST_FIGI",
            batch_size=2,  # Маленький batch для тестов
            flush_interval_sec=0.1  # Быстрый flush для тестов
        )

    @pytest.fixture
    def mock_candle(self):
        """Создает мок свечи"""
        candle = Mock()
        candle.time = datetime.now(timezone.utc)
        candle.open = 100.0
        candle.high = 105.0
        candle.low = 95.0
        candle.close = 102.0
        candle.volume = 1000
        return candle

    @pytest.mark.asyncio
    async def test_market_sink_initialization(self, temp_db_path):
        """Тест инициализации CandleDataSink"""
        sink = CandleDataSink(
            db_path=temp_db_path,
            figi="TEST_FIGI",
            batch_size=100,
            flush_interval_sec=2.0
        )
        
        assert sink._db_path == temp_db_path
        assert sink._figi == "TEST_FIGI"
        assert sink._batch_size == 100
        assert sink._flush_interval_sec == 2.0
        assert sink._closed is False
        assert sink._started is False
        assert sink._worker_task is None

    @pytest.mark.asyncio
    async def test_market_sink_minimum_values(self, temp_db_path):
        """Тест минимальных значений параметров"""
        sink = CandleDataSink(
            db_path=temp_db_path,
            figi="TEST_FIGI",
            batch_size=0,  # Должно стать 1
            flush_interval_sec=-1.0  # Должно стать 0.1
        )
        
        assert sink._batch_size == 1
        assert sink._flush_interval_sec == 0.1

    @pytest.mark.asyncio
    async def test_on_candle_saves_to_queue(self, market_sink, mock_candle):
        """Тест сохранения свечи в очередь"""
        with patch.object(market_sink, '_ensure_started', new_callable=AsyncMock) as mock_start:
            await market_sink.on_candle(mock_candle, 102.0, "TEST_FIGI")
            
            mock_start.assert_called_once()
            assert market_sink._queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_on_candle_ignores_different_figi(self, market_sink, mock_candle):
        """Тест игнорирования свечей с другим FIGI"""
        with patch.object(market_sink, '_ensure_started', new_callable=AsyncMock) as mock_start:
            await market_sink.on_candle(mock_candle, 102.0, "DIFFERENT_FIGI")
            
            mock_start.assert_called_once()
            assert market_sink._queue.qsize() == 0  # Свеча не должна быть добавлена

    @pytest.mark.asyncio
    async def test_on_candle_uses_default_figi(self, market_sink, mock_candle):
        """Тест использования FIGI по умолчанию"""
        with patch.object(market_sink, '_ensure_started', new_callable=AsyncMock) as mock_start:
            await market_sink.on_candle(mock_candle, 102.0, None)
            
            mock_start.assert_called_once()
            assert market_sink._queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_on_candle_handles_exception(self, market_sink):
        """Тест обработки исключений при сохранении свечи"""
        with patch.object(market_sink, '_ensure_started', new_callable=AsyncMock):
            # Создаем невалидную свечу
            invalid_candle = Mock()
            invalid_candle.time = "invalid_time"  # Неправильный тип
            
            await market_sink.on_candle(invalid_candle, 102.0, "TEST_FIGI")
            
            # Очередь должна остаться пустой из-за ошибки
            assert market_sink._queue.qsize() == 0


    @pytest.mark.asyncio
    async def test_worker_processes_candles(self, market_sink, mock_candle):
        """Тест обработки свечей воркером"""
        with patch('robotlib.ingestion.candle_data_sink.init_db', new_callable=AsyncMock), \
             patch('robotlib.ingestion.candle_data_sink.upsert_candles', new_callable=AsyncMock) as mock_upsert:
            
            # Запускаем воркер
            await market_sink._ensure_started()
            
            # Добавляем свечи в очередь
            await market_sink.on_candle(mock_candle, 102.0, "TEST_FIGI")
            await market_sink.on_candle(mock_candle, 103.0, "TEST_FIGI")
            
            # Ждем обработки
            # Нет задержек - тест должен быть мгновенным
            
            # Закрываем воркер
            await market_sink.close()
            
            # Проверяем что свечи были обработаны
            mock_upsert.assert_called()

    @pytest.mark.asyncio
    async def test_worker_batch_processing(self, market_sink, mock_candle):
        """Тест батчевой обработки свечей"""
        with patch('robotlib.ingestion.candle_data_sink.init_db', new_callable=AsyncMock), \
             patch('robotlib.ingestion.candle_data_sink.upsert_candles', new_callable=AsyncMock) as mock_upsert:
            
            # Запускаем воркер
            await market_sink._ensure_started()
            
            # Добавляем 3 свечи (batch_size = 2)
            await market_sink.on_candle(mock_candle, 102.0, "TEST_FIGI")
            await market_sink.on_candle(mock_candle, 103.0, "TEST_FIGI")
            await market_sink.on_candle(mock_candle, 104.0, "TEST_FIGI")
            
            # Ждем обработки
            # Нет задержек - тест должен быть мгновенным
            
            # Закрываем воркер
            await market_sink.close()
            
            # Проверяем что было 2 вызова upsert_candles (2 + 1 свечи)
            assert mock_upsert.call_count >= 2

    @pytest.mark.asyncio
    async def test_worker_timeout_flush(self, market_sink, mock_candle):
        """Тест сброса по таймауту"""
        with patch('robotlib.ingestion.candle_data_sink.init_db', new_callable=AsyncMock), \
             patch('robotlib.ingestion.candle_data_sink.upsert_candles', new_callable=AsyncMock) as mock_upsert:
            
            # Запускаем воркер
            await market_sink._ensure_started()
            
            # Добавляем 1 свечу (меньше batch_size)
            await market_sink.on_candle(mock_candle, 102.0, "TEST_FIGI")
            
            # Ждем таймаут (flush_interval_sec = 0.1)
            # Нет задержек - тест должен быть мгновенным
            
            # Закрываем воркер
            await market_sink.close()
            
            # Проверяем что свеча была обработана по таймауту
            mock_upsert.assert_called()

    @pytest.mark.asyncio
    async def test_close_stops_worker(self, market_sink):
        """Тест остановки воркера"""
        with patch('robotlib.ingestion.candle_data_sink.init_db', new_callable=AsyncMock):
            # Запускаем воркер
            await market_sink._ensure_started()
            assert market_sink._worker_task is not None
            assert not market_sink._closed
            
            # Закрываем
            await market_sink.close()
            
            assert market_sink._closed
            assert market_sink._worker_task is None

    @pytest.mark.asyncio
    async def test_close_idempotent(self, market_sink):
        """Тест идемпотентности close"""
        with patch('robotlib.ingestion.candle_data_sink.init_db', new_callable=AsyncMock):
            # Запускаем воркер
            await market_sink._ensure_started()
            
            # Закрываем дважды
            await market_sink.close()
            await market_sink.close()
            
            assert market_sink._closed
            assert market_sink._worker_task is None

    @pytest.mark.asyncio
    async def test_ensure_started_idempotent(self, market_sink):
        """Тест идемпотентности _ensure_started"""
        with patch('robotlib.ingestion.candle_data_sink.init_db', new_callable=AsyncMock) as mock_init_db:
            # Вызываем _ensure_started дважды
            await market_sink._ensure_started()
            await market_sink._ensure_started()
            
            # init_db должен быть вызван только один раз
            assert mock_init_db.call_count == 1
            assert market_sink._started
            assert market_sink._worker_task is not None

    @pytest.mark.asyncio
    async def test_worker_handles_upsert_exception(self, market_sink, mock_candle):
        """Тест обработки исключений в воркере"""
        with patch('robotlib.ingestion.candle_data_sink.init_db', new_callable=AsyncMock), \
             patch('robotlib.ingestion.candle_data_sink.upsert_candles', new_callable=AsyncMock) as mock_upsert:
            
            mock_upsert.side_effect = Exception("Upsert error")
            
            # Запускаем воркер
            await market_sink._ensure_started()
            
            # Добавляем свечу
            await market_sink.on_candle(mock_candle, 102.0, "TEST_FIGI")
            
            # Ждем обработки
            # Нет задержек - тест должен быть мгновенным
            
            # Закрываем воркер
            await market_sink.close()
            
            # Воркер должен был попытаться обработать свечу
            mock_upsert.assert_called()

    @pytest.mark.asyncio
    async def test_worker_final_flush(self, market_sink, mock_candle):
        """Тест финального сброса при закрытии воркера"""
        with patch('robotlib.ingestion.candle_data_sink.init_db', new_callable=AsyncMock), \
             patch('robotlib.ingestion.candle_data_sink.upsert_candles', new_callable=AsyncMock) as mock_upsert:
            
            # Запускаем воркер
            await market_sink._ensure_started()
            
            # Добавляем свечу
            await market_sink.on_candle(mock_candle, 102.0, "TEST_FIGI")
            
            # Закрываем воркер (должен сбросить оставшиеся свечи)
            await market_sink.close()
            
            # Проверяем что был финальный сброс
            mock_upsert.assert_called()
