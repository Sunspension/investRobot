from datetime import datetime
from unittest.mock import patch

from visualization.formatters import to_moscow_time


def test_to_moscow_time_with_naive_datetime():
    """Тест с naive datetime (без tzinfo) - должен считаться UTC."""
    dt = datetime(2024, 1, 1, 12, 0, 0)  # naive datetime
    result = to_moscow_time(dt)
    
    # Результат должен быть naive datetime в московском времени
    assert result.tzinfo is None
    # В январе МСК = UTC+3, поэтому 12:00 UTC = 15:00 МСК
    assert result.hour == 15
    assert result.minute == 0


def test_to_moscow_time_with_utc_datetime():
    """Тест с UTC datetime."""
    dt = datetime(2024, 1, 1, 12, 0, 0)
    # Добавляем UTC tzinfo
    import pytz
    utc_dt = pytz.utc.localize(dt)
    
    result = to_moscow_time(utc_dt)
    
    # Результат должен быть naive datetime в московском времени
    assert result.tzinfo is None
    assert result.hour == 15  # 12:00 UTC = 15:00 МСК


def test_to_moscow_time_with_moscow_datetime():
    """Тест с уже московским datetime."""
    import pytz
    msk = pytz.timezone('Europe/Moscow')
    dt = datetime(2024, 1, 1, 15, 0, 0)
    msk_dt = msk.localize(dt)
    
    result = to_moscow_time(msk_dt)
    
    # Результат должен быть naive datetime в московском времени
    assert result.tzinfo is None
    assert result.hour == 15


def test_to_moscow_time_with_none():
    """Тест с None - должен вернуть текущее время."""
    result = to_moscow_time(None)
    
    # Результат должен быть naive datetime
    assert result.tzinfo is None
    # Проверяем, что время разумное (не в прошлом)
    now = datetime.now()
    assert result.year >= now.year


@patch('builtins.__import__')
def test_to_moscow_time_pytz_import_error(mock_import):
    """Тест обработки ошибки импорта pytz."""
    def side_effect(name, *args, **kwargs):
        if name == 'pytz':
            raise ImportError("No module named 'pytz'")
        return __import__(name, *args, **kwargs)
    
    mock_import.side_effect = side_effect
    
    dt = datetime(2024, 1, 1, 12, 0, 0)
    result = to_moscow_time(dt)
    
    # При ошибке должен вернуться исходный datetime
    assert result == dt


@patch('builtins.__import__')
def test_to_moscow_time_pytz_error_with_none(mock_import):
    """Тест обработки ошибки pytz с None."""
    def side_effect(name, *args, **kwargs):
        if name == 'pytz':
            raise ImportError("No module named 'pytz'")
        return __import__(name, *args, **kwargs)
    
    mock_import.side_effect = side_effect
    
    result = to_moscow_time(None)
    
    # При ошибке с None должен вернуться текущее время
    assert result.tzinfo is None
    now = datetime.now()
    assert result.year >= now.year
