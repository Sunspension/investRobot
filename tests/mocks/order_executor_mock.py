"""
Мок для исполнителя ордеров - симулирует исполнение ордеров на исторических данных
"""
from datetime import datetime
import uuid
from robotlib.trading.order_types import OrderIntent, OrderExecution, OrderStatus
from robotlib.trading.order_executor import OrderResult

class MockOrderExecutor:
    """Мок для исполнителя ордеров - симулирует исполнение ордеров на исторических данных"""
    
    def __init__(self, **kwargs):
        self._orders = []
        self._success_rate = kwargs.get('success_rate', 1.0)  # 100% успеха по умолчанию
        self._mock_prices = kwargs.get('mock_prices', {})  # Мок цены для разных FIGI
        self._executions = []  # Список исполненных ордеров
        self._commission_rate = kwargs.get('commission_rate', 0.01)  # 1% комиссия
    
    async def execute_order(self, order_intent: OrderIntent) -> OrderExecution:
        """
        Симулирует исполнение OrderIntent на исторических данных
        """
        # Генерируем уникальный ID для ордера
        order_id = str(uuid.uuid4())
        
        # Получаем цену исполнения (используем цену из свечи или мок цену)
        if order_intent.figi in self._mock_prices:
            executed_price = self._mock_prices[order_intent.figi]
        else:
            # Для тестирования используем фиксированную цену
            executed_price = 1500.0  # Базовая цена для фьючерса
        
        # Симулируем успешное исполнение
        success = self._success_rate >= 1.0
        
        if success:
            executed_quantity = order_intent.quantity
            status = OrderStatus.FILLED
        else:
            executed_quantity = 0
            status = OrderStatus.REJECTED
        
        # Рассчитываем комиссию
        commission = executed_price * executed_quantity * self._commission_rate
        
        # Создаем OrderExecution
        execution = OrderExecution(
            order_id=order_id,
            intent=order_intent,
            executed_price=executed_price,
            executed_quantity=executed_quantity,
            executed_at=datetime.now(),
            status=status,
            commission=commission
        )
        
        # Сохраняем исполнение для анализа
        self._executions.append(execution)
        
        return execution
    
    async def buy_market(self, figi: str, quantity: int, wait_execution: bool = True) -> OrderResult:
        """Мок покупки по рыночной цене"""
        success = self._success_rate >= 1.0
        self._orders.append(('buy', figi, quantity))
        
        return OrderResult(
            success=success,
            order_id=f"mock_buy_{len(self._orders)}",
            error_message=None if success else "Mock error",
            executed_price=100.0 if success else None,
            executed_quantity=quantity if success else 0,
            order_status="FILL" if success else "REJECTED",
            is_executed=success
        )
    
    async def sell_market(self, figi: str, quantity: int, wait_execution: bool = True) -> OrderResult:
        """Мок продажи по рыночной цене"""
        success = self._success_rate >= 1.0
        self._orders.append(('sell', figi, quantity))
        
        return OrderResult(
            success=success,
            order_id=f"mock_sell_{len(self._orders)}",
            error_message=None if success else "Mock error",
            executed_price=105.0 if success else None,
            executed_quantity=quantity if success else 0,
            order_status="FILL" if success else "REJECTED",
            is_executed=success
        )
    
    async def buy_limit(self, figi: str, quantity: int, price: float) -> OrderResult:
        """Мок покупки по лимитной цене"""
        success = self._success_rate >= 1.0
        self._orders.append(('buy_limit', figi, quantity, price))
        
        return OrderResult(
            success=success,
            order_id=f"mock_buy_limit_{len(self._orders)}",
            error_message=None if success else "Mock error"
        )
    
    async def sell_limit(self, figi: str, quantity: int, price: float) -> OrderResult:
        """Мок продажи по лимитной цене"""
        success = self._success_rate >= 1.0
        self._orders.append(('sell_limit', figi, quantity, price))
        
        return OrderResult(
            success=success,
            order_id=f"mock_sell_limit_{len(self._orders)}",
            error_message=None if success else "Mock error"
        )
