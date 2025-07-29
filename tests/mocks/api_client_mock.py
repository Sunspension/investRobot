"""
Мок для API клиента для тестирования на исторических данных
"""
from robotlib.utils.logger import get_logger
from robotlib.trading.order_executor import OrderResult

logger = get_logger(__name__)

class MockAPIClient:
    """Мок API клиента для тестирования на исторических данных"""
    
    def __init__(self, deposit: float = 400000):
        self.deposit = deposit
        self.logger = get_logger(__name__)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def get_portfolio(self):
        """Возвращает мок портфеля"""
        class MockPortfolioResponse:
            def __init__(self, total_amount):
                self.total_amount = total_amount
                self.positions = []
        
        return MockPortfolioResponse(self.deposit)
    
    async def get_candles(self, figi: str, from_date, to_date, interval):
        """Возвращает мок свечей (пустой ответ для тестирования)"""
        class MockCandlesResponse:
            def __init__(self):
                self.candles = []
        return MockCandlesResponse()
    
    async def buy_market(self, figi: str, quantity: int, wait_execution: bool = True):
        """Мок покупки по рыночной цене"""
        return OrderResult(
            success=True,
            order_id=f"mock_buy_{quantity}",
            executed_price=1500.0,
            executed_quantity=quantity,
            commission=15.0
        )
    
    async def sell_market(self, figi: str, quantity: int, wait_execution: bool = True):
        """Мок продажи по рыночной цене"""
        return OrderResult(
            success=True,
            order_id=f"mock_sell_{quantity}",
            executed_price=1500.0,
            executed_quantity=quantity,
            commission=15.0
        )
    
    async def buy_limit(self, figi: str, quantity: int, price: float, wait_execution: bool = True):
        """Мок покупки по лимитной цене"""
        return OrderResult(
            success=True,
            order_id=f"mock_buy_limit_{quantity}",
            executed_price=price,
            executed_quantity=quantity,
            commission=15.0
        )
    
    async def sell_limit(self, figi: str, quantity: int, price: float, wait_execution: bool = True):
        """Мок продажи по лимитной цене"""
        return OrderResult(
            success=True,
            order_id=f"mock_sell_limit_{quantity}",
            executed_price=price,
            executed_quantity=quantity,
            commission=15.0
        )
    
    async def can_buy(self, figi: str, quantity: int) -> bool:
        """Возвращает мок возможности покупки"""
        return True
    
    async def can_sell(self, figi: str, quantity: int) -> bool:
        """Возвращает мок возможности продажи"""
        return True
