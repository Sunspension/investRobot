"""
Мок для менеджера портфеля для тестирования
"""
from robotlib.utils.logger import get_logger

logger = get_logger(__name__)

class MockPortfolioManager:
    """Мок менеджер портфеля для тестирования"""
    
    def __init__(self, api_client=None, **kwargs):
        self.api_client = api_client
        self.logger = get_logger(__name__)
        
        # Поддержка параметров для тестирования
        self._deposit = kwargs.get('deposit', 100000.0)
        self._guarantee_deposit = kwargs.get('guarantee_deposit', 10000.0)
    
    async def get_available_money(self) -> float:
        """Возвращает доступные средства"""
        if self.api_client:
            portfolio = await self.api_client.get_portfolio()
            return portfolio.total_amount
        return self._deposit
    
    async def get_deposit(self) -> float:
        """Возвращает депозит"""
        if self.api_client:
            return await self.get_available_money()
        return self._deposit
    
    async def get_guarantee_deposit(self, figi: str) -> float:
        """Возвращает гарантийный депозит для инструмента"""
        return self._guarantee_deposit
    
    async def can_buy(self, figi: str, quantity: int) -> bool:
        """Проверяет возможность покупки"""
        if self.api_client:
            return await self.api_client.can_buy(figi, quantity)
        return True  # В тестах всегда разрешаем
    
    async def can_sell(self, figi: str, quantity: int) -> bool:
        """Проверяет возможность продажи"""
        if self.api_client:
            return await self.api_client.can_sell(figi, quantity)
        return True  # В тестах всегда разрешаем
