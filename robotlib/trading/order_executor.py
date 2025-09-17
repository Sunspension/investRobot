"""
Модуль для выполнения реальных торговых приказов через Tinkoff API
"""

from typing import Optional
from robotlib.trading.tinkoff_api_client import TinkoffAPIClient, OrderResult
from robotlib.ingestion.db_sink import DBIngestionSink
from robotlib.trading.order_types import OrderIntent, OrderExecution, OrderDirection, OrderType, OrderStatus
from robotlib.utils.logger import get_logger
from config_data.config import load_config
from datetime import datetime
import asyncio
import uuid


class OrderExecutor:
    """Класс для выполнения торговых приказов"""
    
    def __init__(
        self, api_client: TinkoffAPIClient, 
        order_sink: Optional[DBIngestionSink] = None
    ):
        """
        Инициализация исполнителя приказов
        
        Args:
            api_client: API клиент для работы с Tinkoff
            order_sink: Приёмник исполненных ордеров
        """
        self.api_client = api_client
        self._order_sink = order_sink
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
            if order_intent.direction == OrderDirection.BUY:
                dir_text = "лонг" if (result.executed_quantity or 0) > 0 else "покупка"
            else:
                dir_text = "шорт" if (result.executed_quantity or 0) > 0 else "продажа"

            exec_reason = f"{dir_text} {order_intent.quantity} шт."

            execution = OrderExecution(
                order_id=order_id,
                figi=order_intent.figi,
                direction=order_intent.direction,
                quantity=order_intent.quantity,
                filled_quantity=result.executed_quantity or 0,
                price=result.executed_price or 0.0,
                status=OrderStatus.FILLED if result.success else OrderStatus.REJECTED,
                timestamp=datetime.now(),
                error_message=None if result.success else getattr(result, 'error_message', None),
                commission=result.commission or 0.0,
                reason=exec_reason
            )
            
            # Если ордер исполнен, записываем в БД (если sink задан)
            if result.success and execution.status == OrderStatus.FILLED and self._order_sink is not None:
                try:
                    order_record = {
                        'order_id': execution.order_id,
                        'account_id': getattr(self.api_client, 'account_id', None),
                        'figi': order_intent.figi,
                        'time': execution.timestamp,
                        'type': 'buy' if order_intent.direction.name.lower() == 'buy' else 'sell',
                        'price': execution.price or 0.0,
                        'quantity': execution.filled_quantity or order_intent.quantity,
                        'status': 'filled',
                        'commission': execution.commission or 0.0,
                        'strategy': getattr(order_intent, 'strategy', None),
                        'reason': execution.reason,
                    }
                    await self._order_sink.on_order(order_record)
                except Exception as persist_err:
                    self.logger.warning(f"Не удалось сохранить исполненный ордер: {persist_err}")
            
            self.logger.info(f"Ордер выполнен: {execution}")
            return execution
            
        except Exception as e:
            self.logger.error(f"Ошибка выполнения ордера {order_intent}: {e}")
            
            # Создаем OrderExecution с ошибкой
            execution = OrderExecution(
                order_id=str(uuid.uuid4()),
                figi=order_intent.figi,
                direction=order_intent.direction,
                quantity=order_intent.quantity,
                filled_quantity=0,
                price=0.0,
                status=OrderStatus.REJECTED,
                timestamp=datetime.now(),
                error_message=str(e),
                commission=0.0,
                reason="ошибка выполнения"
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
