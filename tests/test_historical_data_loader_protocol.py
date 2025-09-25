#!/usr/bin/env python3
"""
Тесты для демонстрации гибкости протокола HistoricalDataLoaderable
"""
import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timezone, timedelta
from tinkoff.invest import Candle, MoneyValue

from robotlib.trading.historical_data_loader import HistoricalDataLoader
from robotlib.trading.historical_data_loader_interfaces import HistoricalDataLoaderable
from robotlib.trading.file_historical_data_loader import FileHistoricalDataLoader


class MockHistoricalDataLoader:
    """Mock реализация HistoricalDataLoaderable для тестов"""
    
    def __init__(self):
        self._candles = []
        self._last_main_session = None
        self._last_trading_session = None
    
    async def load_historical_data(self, from_date: datetime, to_date: datetime) -> list:
        return self._candles
    
    async def gap_fill_missing_candles(self, last_candle_time: datetime, sink) -> None:
        if sink:
            for candle in self._candles:
                await sink.on_candle(candle, 1000.0, "TEST")
    
    async def get_last_main_trading_session_period(self) -> tuple:
        if self._last_main_session:
            return self._last_main_session
        return datetime.now(timezone.utc), datetime.now(timezone.utc)
    
    async def get_last_trading_session_period(self) -> tuple:
        if self._last_trading_session:
            return self._last_trading_session
        return datetime.now(timezone.utc), datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_historical_data_loader_protocol_compliance():
    """Тест, что все реализации соответствуют протоколу HistoricalDataLoaderable"""
    
    # Создаем тестовые данные
    mock_candle = Mock(spec=Candle)
    mock_candle.close = MoneyValue(units=1000, nano=500000000)  # 1000.5
    mock_candle.time = datetime.now(timezone.utc)
    
    from_date = datetime.now(timezone.utc) - timedelta(days=1)
    to_date = datetime.now(timezone.utc)
    
    # Тестируем стандартную реализацию
    api_client = Mock()
    standard_loader = HistoricalDataLoader(api_client, "FUTIMOEXF000")
    await _test_loader_implementation(standard_loader, mock_candle, from_date, to_date, "HistoricalDataLoader")
    
    # Тестируем файловую реализацию
    file_loader = FileHistoricalDataLoader(api_client, "FUTIMOEXF000")
    await _test_loader_implementation(file_loader, mock_candle, from_date, to_date, "FileHistoricalDataLoader")
    
    # Тестируем mock реализацию
    mock_loader = MockHistoricalDataLoader()
    await _test_loader_implementation(mock_loader, mock_candle, from_date, to_date, "MockHistoricalDataLoader")


async def _test_loader_implementation(
    loader: HistoricalDataLoaderable, 
    candle: Candle, 
    from_date: datetime, 
    to_date: datetime, 
    loader_name: str
):
    """Вспомогательная функция для тестирования реализации загрузчика"""
    
    # Тестируем загрузку исторических данных
    candles = await loader.load_historical_data(from_date, to_date)
    assert isinstance(candles, list), f"{loader_name}: load_historical_data должен возвращать список"
    
    # Тестируем gap-fill
    mock_sink = Mock()
    mock_sink.on_candle = AsyncMock()
    await loader.gap_fill_missing_candles(from_date, mock_sink)
    # Проверяем, что метод выполнился без ошибок
    
    # Тестируем получение периода основной сессии
    main_session = await loader.get_last_main_trading_session_period()
    assert isinstance(main_session, tuple), f"{loader_name}: get_last_main_trading_session_period должен возвращать кортеж"
    assert len(main_session) == 2, f"{loader_name}: кортеж должен содержать 2 элемента (начало, конец)"
    assert isinstance(main_session[0], datetime), f"{loader_name}: первый элемент должен быть datetime"
    assert isinstance(main_session[1], datetime), f"{loader_name}: второй элемент должен быть datetime"
    
    # Тестируем получение периода торговой сессии
    trading_session = await loader.get_last_trading_session_period()
    assert isinstance(trading_session, tuple), f"{loader_name}: get_last_trading_session_period должен возвращать кортеж"
    assert len(trading_session) == 2, f"{loader_name}: кортеж должен содержать 2 элемента (начало, конец)"
    assert isinstance(trading_session[0], datetime), f"{loader_name}: первый элемент должен быть datetime"
    assert isinstance(trading_session[1], datetime), f"{loader_name}: второй элемент должен быть datetime"


@pytest.mark.asyncio
async def test_protocol_flexibility():
    """Тест демонстрирует гибкость использования протокола"""
    
    # Функция, которая работает с любым загрузчиком, реализующим протокол
    async def process_historical_data(loader: HistoricalDataLoaderable, from_date: datetime, to_date: datetime):
        """Обрабатывает исторические данные через любой загрузчик"""
        
        # Загружаем данные
        candles = await loader.load_historical_data(from_date, to_date)
        
        # Получаем периоды сессий
        main_session = await loader.get_last_main_trading_session_period()
        trading_session = await loader.get_last_trading_session_period()
        
        # Gap-fill
        mock_sink = Mock()
        mock_sink.on_candle = AsyncMock()
        await loader.gap_fill_missing_candles(from_date, mock_sink)
        
        return {
            'candles_count': len(candles),
            'main_session': main_session,
            'trading_session': trading_session,
            'gap_fill_called': mock_sink.on_candle.called
        }
    
    # Создаем тестовые данные
    from_date = datetime.now(timezone.utc) - timedelta(days=1)
    to_date = datetime.now(timezone.utc)
    
    # Тестируем с разными реализациями загрузчика
    api_client = Mock()
    implementations = [
        HistoricalDataLoader(api_client, "FUTIMOEXF000"),
        FileHistoricalDataLoader(api_client, "FUTIMOEXF000"),
        MockHistoricalDataLoader(),
    ]
    
    for loader in implementations:
        result = await process_historical_data(loader, from_date, to_date)
        
        # Проверяем, что функция работает с любой реализацией
        assert isinstance(result['candles_count'], int)
        assert isinstance(result['main_session'], tuple)
        assert isinstance(result['trading_session'], tuple)
        assert isinstance(result['gap_fill_called'], bool)


if __name__ == "__main__":
    pytest.main([__file__])
