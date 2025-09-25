"""
Пакет для сохранения торговых данных в базу данных.

Содержит специализированные приёмники для различных типов данных:
- CandleDataSink: для свечей
- OrderExecutionSink: для исполненных ордеров
"""

from .candle_data_sink import CandleDataSink
from .order_execution_sink import OrderExecutionSink

__all__ = ['CandleDataSink', 'OrderExecutionSink']
