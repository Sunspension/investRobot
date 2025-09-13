"""
Модуль для выполнения реальных торговых приказов через Tinkoff API
"""

from typing import Optional
from robotlib.trading.tinkoff_api_client import TinkoffAPIClient, OrderResult
from robotlib.trading.event_bus_interface import EventBusable, EventType, TradingEvent
from robotlib.trading.order_types import OrderIntent, OrderExecution, OrderDirection, OrderType, OrderStatus
from robotlib.utils.logger import get_logger
from config_data.config import load_config
from datetime import datetime
import asyncio
import uuid


class OrderExecutor:
    """Класс для выполнения торговых приказов"""
    
    def __init__(self, api_client: TinkoffAPIClient, event_bus: Optional[EventBusable] = None):
        """
        Инициализация исполнителя приказов
        
        Args:
            api_client: API клиент для работы с Tinkoff
            event_bus: Шина событий для публикации событий ордеров
        """
        self.api_client = api_client
        self._event_bus = event_bus
        self.logger = get_logger(__name__)
    
    async def check_market_availability(self) -> bool:
        """Проверяет доступность рынка для торговли"""
        return await self.api_client.check_market_availability()
    
    async def execute_order(self, order_intent: OrderIntent) -> OrderExecution:
        """
        Выполняет OrderIntent и возвращает OrderExecution
        
        Args:
            order_intent: Намерение на совершение сделки
            
        Returns:
            OrderExecution: Результат исполнения ордера
        """
        self.logger.info(f"Выполнение ордера: {order_intent}")
        
        try:
            # Генерируем уникальный ID для ордера
            order_id = str(uuid.uuid4())
            
            # Выполняем ордер в зависимости от типа
            if order_intent.order_type == OrderType.MARKET:
                result = await self._execute_market_order(order_intent)
            elif order_intent.order_type == OrderType.LIMIT:
                result = await self._execute_limit_order(order_intent)
            else:
                raise ValueError(f"Неподдерживаемый тип ордера: {order_intent.order_type}")
            
            # Создаем OrderExecution
            execution = OrderExecution(
                order_id=order_id,
                intent=order_intent,
                executed_price=result.executed_price,
                executed_quantity=result.executed_quantity,
                executed_at=datetime.now(),
                status=OrderStatus.FILLED if result.success else OrderStatus.REJECTED,
                commission=result.commission or 0.0
            )
            
            # Публикуем событие размещения ордера
            if self._event_bus:
                placed_event = TradingEvent(
                    EventType.ORDER_PLACED,
                    {
                        'order_id': order_id,
                        'order_intent': order_intent,
                        'execution': execution,
                        'result': result
                    }
                )
                asyncio.create_task(self._event_bus.publish(placed_event))
            
            # Если ордер исполнен, публикуем событие исполнения
            if result.success and execution.status == OrderStatus.FILLED:
                if self._event_bus:
                    filled_event = TradingEvent(
                        EventType.ORDER_FILLED,
                        {
                            'order_id': order_id,
                            'execution': execution,
                            'executed_price': result.executed_price,
                            'executed_quantity': result.executed_quantity,
                            'commission': result.commission or 0.0
                        }
                    )
                    asyncio.create_task(self._event_bus.publish(filled_event))
            
            self.logger.info(f"Ордер выполнен: {execution}")
            return execution
            
        except Exception as e:
            self.logger.error(f"Ошибка выполнения ордера {order_intent}: {e}")
            
            # Создаем OrderExecution с ошибкой
            execution = OrderExecution(
                order_id=str(uuid.uuid4()),
                intent=order_intent,
                executed_price=0.0,
                executed_quantity=0,
                executed_at=datetime.now(),
                status=OrderStatus.REJECTED,
                commission=0.0
            )
            
            return execution
    
    async def _execute_market_order(self, order_intent: OrderIntent) -> OrderResult:
        """Выполняет рыночный ордер"""
        if order_intent.direction == OrderDirection.BUY:
            return await self.api_client.buy_market(
                figi=order_intent.figi,
                quantity=order_intent.quantity,
                wait_execution=True
            )
        elif order_intent.direction == OrderDirection.SELL:
            return await self.api_client.sell_market(
                figi=order_intent.figi,
                quantity=order_intent.quantity,
                wait_execution=True
            )
        else:
            raise ValueError(f"Неподдерживаемое направление ордера: {order_intent.direction}")
    
    async def _execute_limit_order(self, order_intent: OrderIntent) -> OrderResult:
        """Выполняет лимитный ордер"""
        if order_intent.limit_price is None:
            raise ValueError("Для лимитного ордера необходимо указать limit_price")
        
        if order_intent.direction == OrderDirection.BUY:
            return await self.api_client.buy_limit(
                figi=order_intent.figi,
                quantity=order_intent.quantity,
                price=order_intent.limit_price
            )
        elif order_intent.direction == OrderDirection.SELL:
            return await self.api_client.sell_limit(
                figi=order_intent.figi,
                quantity=order_intent.quantity,
                price=order_intent.limit_price
            )
        else:
            raise ValueError(f"Неподдерживаемое направление ордера: {order_intent.direction}")
    
    async def place_order(
        self,
        figi: str,
        direction,
        quantity: int,
        price: Optional[float] = None,
        order_type=None
    ) -> OrderResult:
        """Размещает торговый приказ"""
        return await self.api_client.place_order(figi, direction, quantity, price, order_type)
    
    async def get_order_status(self, order_id: str):
        """Получает статус приказа"""
        return await self.api_client.get_order_status(order_id)
    
    async def cancel_order(self, order_id: str) -> bool:
        """Отменяет приказ"""
        return await self.api_client.cancel_order(order_id)
    
    async def buy_market(self, figi: str, quantity: int, wait_execution: bool = True) -> OrderResult:
        """Покупка по рыночной цене"""
        return await self.api_client.buy_market(figi, quantity, wait_execution)
    
    async def sell_market(self, figi: str, quantity: int, wait_execution: bool = True) -> OrderResult:
        """Продажа по рыночной цене"""
        return await self.api_client.sell_market(figi, quantity, wait_execution)
    
    async def buy_limit(self, figi: str, quantity: int, price: float) -> OrderResult:
        """Покупка по лимитной цене"""
        return await self.api_client.buy_limit(figi, quantity, price)
    
    async def sell_limit(self, figi: str, quantity: int, price: float) -> OrderResult:
        """Продажа по лимитной цене"""
        return await self.api_client.sell_limit(figi, quantity, price)
    
# Пример использования
async def main():
    """Пример использования OrderExecutor"""
    logger = get_logger(__name__)
    config = load_config()
    
    async with TinkoffAPIClient(
        token=config.tcs_client.token,
        account_id=config.tcs_client.id,
        sandbox_token=config.tcs_client.sandbox_token
    ) as api_client:
        
        executor = OrderExecutor(api_client)
        
        # Проверяем доступность рынка
        if await executor.check_market_availability():
            logger.info("Рынок доступен для торговли")
            
            # Пример покупки
            result = await executor.buy_market(
                figi="FUTIMOEXF000",
                quantity=1
            )
            
            if result.success:
                logger.info(f"Покупка выполнена: {result.order_id}")
            else:
                logger.error(f"Ошибка покупки: {result.error_message}")
        else:
            logger.warning("Рынок недоступен")


if __name__ == "__main__":
    asyncio.run(main())
