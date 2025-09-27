"""
Пример восстановления позиций из API операций

Этот пример показывает, как использовать PositionRestorationService
для восстановления FIFO записей из истории операций API.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock
from tinkoff.invest.schemas import MoneyValue

from robotlib.trading.position_restoration_service import PositionRestorationService
from robotlib.trading.position_restoration_interface import Position


async def main():
    """Пример использования PositionRestorationService"""
    
    # Создаем мок API клиента
    mock_api_client = AsyncMock()
    
    # Настраиваем мок для возврата операций
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
    
    # Настраиваем ответ API
    operations_response = Mock()
    operations_response.operations = operations_list
    mock_api_client.get_operations_history = AsyncMock(return_value=operations_response)
    mock_api_client.get_operations_by_cursor = AsyncMock(return_value=operations_response)
    mock_api_client._sandbox_token = "test_token"
    
    # Создаем сервис восстановления
    restoration_service = PositionRestorationService(mock_api_client, point_value=10.0)
    
    # Создаем позицию для восстановления
    api_positions = {
        'FUTIMOEXF000': Position(
            figi='FUTIMOEXF000',
            quantity=6,  # 5 + 3 - 2 = 6
            avg_price=2700.8,
            last_updated=datetime.now()
        )
    }
    
    existing_fifo = {}
    
    print("🔄 Восстанавливаем FIFO из API операций...")
    
    # Восстанавливаем FIFO
    result = await restoration_service.restore_fifo_from_api(api_positions, existing_fifo)
    
    print(f"✅ Результат восстановления: {len(result)} инструментов")
    
    if 'FUTIMOEXF000' in result:
        fifo_entries = result['FUTIMOEXF000']
        print(f"📊 Восстановлено {len(fifo_entries)} FIFO записей для FUTIMOEXF000")
        
        # Показываем первые несколько записей
        for i, entry in enumerate(fifo_entries[:3]):
            print(f"  {i+1}. {entry.direction.upper()} {entry.quantity} лотов по {entry.price/10.0:.1f} (ID: {entry.order_id})")
    
    print("🎯 Пример завершен!")


if __name__ == "__main__":
    asyncio.run(main())
