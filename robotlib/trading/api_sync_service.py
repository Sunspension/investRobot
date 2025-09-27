"""
Сервис синхронизации с API Tinkoff как источником правды
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from robotlib.trading.tinkoff_api_client import TinkoffAPIClient
from robotlib.utils.enhanced_sql_schema import (
    Operation, Trade, Order, SyncStatus,
    money_value_to_dict, convert_money_to_rubles
)
from robotlib.utils.logger import get_logger
from config_data.config import load_config


class APISyncService:
    """Сервис синхронизации с API Tinkoff"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = get_logger(__name__)
        self.config = load_config()
        self.api_client: Optional[TinkoffAPIClient] = None
        
    async def __aenter__(self):
        """Инициализация API клиента"""
        self.api_client = TinkoffAPIClient(
            token=self.config.tcs_client.token,
            account_id=self.config.tcs_client.account_id,
            sandbox_token=self.config.tcs_client.sandbox_token
        )
        await self.api_client.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрытие API клиента"""
        if self.api_client:
            await self.api_client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def sync_operations(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Синхронизация операций с API"""
        self.logger.info(f"🔄 Синхронизация операций с {start_date.date()} по {end_date.date()}")
        
        try:
            # Получаем операции из API
            operations_response = await self.api_client.get_operations_history(start_date, end_date)
            
            if not hasattr(operations_response, 'operations'):
                raise ValueError("Не удалось получить операции из API")
            
            operations = operations_response.operations
            self.logger.info(f"📊 Получено {len(operations)} операций из API")
            
            # Сохраняем операции в БД
            saved_operations = 0
            saved_trades = 0
            
            for operation in operations:
                # Сохраняем операцию
                await self._save_operation(operation)
                saved_operations += 1
                
                # Сохраняем сделки
                if hasattr(operation, 'trades') and operation.trades:
                    for trade in operation.trades:
                        await self._save_trade(trade, operation.id)
                        saved_trades += 1
            
            # Обновляем статус синхронизации
            await self._update_sync_status("operations", end_date, operations[-1].id if operations else None, "success")
            
            result = {
                "status": "success",
                "operations_saved": saved_operations,
                "trades_saved": saved_trades,
                "date_range": f"{start_date.date()} - {end_date.date()}"
            }
            
            self.logger.info(f"✅ Синхронизация завершена: {saved_operations} операций, {saved_trades} сделок")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка синхронизации: {e}")
            await self._update_sync_status("operations", end_date, None, "error", str(e))
            raise
    
    async def sync_orders(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Синхронизация ордеров (агрегированных данных)"""
        self.logger.info(f"🔄 Синхронизация ордеров с {start_date.date()} по {end_date.date()}")
        
        try:
            # Получаем операции из БД
            operations = await self._get_operations_for_period(start_date, end_date)
            
            # Агрегируем в ордера
            orders_created = 0
            
            for operation in operations:
                if operation.operation_type in [15, 16]:  # Покупка/продажа
                    # Получаем сделки для операции
                    trades = await self._get_trades_for_operation(operation.id)
                    
                    for trade in trades:
                        # Создаем ордер
                        order = await self._create_order_from_trade(operation, trade)
                        await self._save_order(order)
                        orders_created += 1
            
            # Обновляем статус синхронизации
            await self._update_sync_status("orders", end_date, None, "success")
            
            result = {
                "status": "success",
                "orders_created": orders_created,
                "date_range": f"{start_date.date()} - {end_date.date()}"
            }
            
            self.logger.info(f"✅ Синхронизация ордеров завершена: {orders_created} ордеров")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка синхронизации ордеров: {e}")
            await self._update_sync_status("orders", end_date, None, "error", str(e))
            raise
    
    async def restore_from_api(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Полное восстановление данных из API"""
        self.logger.info(f"🔄 Полное восстановление данных с {start_date.date()} по {end_date.date()}")
        
        try:
            # Синхронизируем операции
            operations_result = await self.sync_operations(start_date, end_date)
            
            # Синхронизируем ордера
            orders_result = await self.sync_orders(start_date, end_date)
            
            result = {
                "status": "success",
                "operations": operations_result,
                "orders": orders_result,
                "total_restored": operations_result["operations_saved"] + orders_result["orders_created"]
            }
            
            self.logger.info(f"✅ Восстановление завершено: {result['total_restored']} записей")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка восстановления: {e}")
            raise
    
    async def get_sync_status(self) -> Dict[str, SyncStatus]:
        """Получение статуса синхронизации"""
        import aiosqlite
        
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute("SELECT * FROM sync_status ORDER BY updated_at DESC") as cur:
                rows = await cur.fetchall()
                
            statuses = {}
            for row in rows:
                sync_type = row[1]
                statuses[sync_type] = SyncStatus(
                    sync_type=sync_type,
                    last_sync_date=datetime.fromisoformat(row[2]) if row[2] else None,
                    last_operation_id=row[3],
                    sync_status=row[4],
                    error_message=row[5]
                )
            
            return statuses
    
    # Приватные методы
    async def _save_operation(self, operation) -> None:
        """Сохранение операции в БД"""
        import aiosqlite
        
        operation_data = {
            "id": operation.id,
            "operation_type": operation.operation_type,
            "date": operation.date.isoformat(),
            "figi": operation.figi,
            "instrument_type": getattr(operation, 'instrument_type', None),
            "quantity": operation.quantity,
            "quantity_rest": getattr(operation, 'quantity_rest', 0),
            "operation_description": getattr(operation, 'type', None),
            "state": getattr(operation, 'state', None),
            "parent_operation_id": getattr(operation, 'parent_operation_id', None),
            "position_uid": getattr(operation, 'position_uid', None),
            "instrument_uid": getattr(operation, 'instrument_uid', None),
            "asset_uid": getattr(operation, 'asset_uid', None),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        # Добавляем данные о деньгах
        if hasattr(operation, 'price') and operation.price:
            price_data = money_value_to_dict(operation.price)
            operation_data.update({
                "price_currency": price_data["currency"],
                "price_units": price_data["units"],
                "price_nano": price_data["nano"]
            })
        
        if hasattr(operation, 'payment') and operation.payment:
            payment_data = money_value_to_dict(operation.payment)
            operation_data.update({
                "payment_currency": payment_data["currency"],
                "payment_units": payment_data["units"],
                "payment_nano": payment_data["nano"]
            })
        
        if hasattr(operation, 'commission') and operation.commission:
            commission_data = money_value_to_dict(operation.commission)
            operation_data.update({
                "commission_currency": commission_data["currency"],
                "commission_units": commission_data["units"],
                "commission_nano": commission_data["nano"]
            })
        
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                INSERT OR REPLACE INTO operations (
                    id, operation_type, date, figi, instrument_type, quantity, quantity_rest,
                    price_currency, price_units, price_nano,
                    payment_currency, payment_units, payment_nano,
                    commission_currency, commission_units, commission_nano,
                    operation_description, state, parent_operation_id, position_uid,
                    instrument_uid, asset_uid, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                operation_data["id"], operation_data["operation_type"], operation_data["date"],
                operation_data["figi"], operation_data["instrument_type"], operation_data["quantity"],
                operation_data["quantity_rest"], operation_data.get("price_currency"),
                operation_data.get("price_units"), operation_data.get("price_nano"),
                operation_data.get("payment_currency"), operation_data.get("payment_units"),
                operation_data.get("payment_nano"), operation_data.get("commission_currency"),
                operation_data.get("commission_units"), operation_data.get("commission_nano"),
                operation_data["operation_description"], operation_data["state"],
                operation_data["parent_operation_id"], operation_data["position_uid"],
                operation_data["instrument_uid"], operation_data["asset_uid"],
                operation_data["created_at"], operation_data["updated_at"]
            ))
            await conn.commit()
    
    async def _save_trade(self, trade, operation_id: str) -> None:
        """Сохранение сделки в БД"""
        import aiosqlite
        
        trade_data = {
            "trade_id": trade.trade_id,
            "operation_id": operation_id,
            "date_time": trade.date_time.isoformat(),
            "quantity": trade.quantity,
            "created_at": datetime.now().isoformat()
        }
        
        # Добавляем данные о цене
        if hasattr(trade, 'price') and trade.price:
            price_data = money_value_to_dict(trade.price)
            trade_data.update({
                "price_currency": price_data["currency"],
                "price_units": price_data["units"],
                "price_nano": price_data["nano"]
            })
        
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                INSERT OR REPLACE INTO trades (
                    trade_id, operation_id, date_time, quantity,
                    price_currency, price_units, price_nano, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_data["trade_id"], trade_data["operation_id"], trade_data["date_time"],
                trade_data["quantity"], trade_data.get("price_currency"),
                trade_data.get("price_units"), trade_data.get("price_nano"),
                trade_data["created_at"]
            ))
            await conn.commit()
    
    async def _save_order(self, order: Order) -> None:
        """Сохранение ордера в БД"""
        import aiosqlite
        
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                INSERT OR REPLACE INTO orders (
                    order_id, account_id, figi, time, direction, price, quantity,
                    status, commission, strategy, reason, operation_id, trade_id,
                    execution_time, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order.order_id, order.account_id, order.figi, order.time.isoformat(),
                order.direction, order.price, order.quantity, order.status,
                order.commission, order.strategy, order.reason, order.operation_id,
                order.trade_id, order.execution_time.isoformat() if order.execution_time else None,
                datetime.now().isoformat(), datetime.now().isoformat()
            ))
            await conn.commit()
    
    async def _create_order_from_trade(self, operation, trade) -> Order:
        """Создание ордера из сделки"""
        # Определяем направление
        direction = "buy" if operation.operation_type == 15 else "sell"
        
        # Конвертируем цену в рубли
        price = 0.0
        if hasattr(trade, 'price') and trade.price:
            from robotlib.utils.money import money_value_to_float_with_currency
            price = money_value_to_float_with_currency(trade.price, point_value=10.0)
        
        # Конвертируем комиссию в рубли
        commission = 0.0
        if hasattr(operation, 'commission') and operation.commission:
            from robotlib.utils.money import money_value_to_float_with_currency
            commission = money_value_to_float_with_currency(operation.commission, point_value=1.0)  # Комиссия обычно в рублях
        
        return Order(
            order_id=trade.trade_id,  # Используем ID сделки как ID ордера
            account_id=self.config.tcs_client.account_id,
            figi=operation.figi,
            time=trade.date_time,
            direction=direction,
            price=price,
            quantity=trade.quantity,
            status="filled",
            commission=commission,
            strategy="api_sync",
            reason=f"Синхронизация с API: {operation.operation_type}",
            operation_id=operation.id,
            trade_id=trade.trade_id,
            execution_time=trade.date_time
        )
    
    async def _get_operations_for_period(self, start_date: datetime, end_date: datetime) -> List[Operation]:
        """Получение операций за период из БД"""
        import aiosqlite
        
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute("""
                SELECT * FROM operations 
                WHERE date BETWEEN ? AND ? 
                ORDER BY date DESC
            """, (start_date.isoformat(), end_date.isoformat())) as cur:
                rows = await cur.fetchall()
                
            operations = []
            for row in rows:
                operations.append(Operation(
                    id=row[0],
                    operation_type=row[1],
                    date=datetime.fromisoformat(row[2]),
                    figi=row[3],
                    instrument_type=row[4],
                    quantity=row[5],
                    quantity_rest=row[6],
                    price_currency=row[7],
                    price_units=row[8],
                    price_nano=row[9],
                    payment_currency=row[10],
                    payment_units=row[11],
                    payment_nano=row[12],
                    commission_currency=row[13],
                    commission_units=row[14],
                    commission_nano=row[15],
                    operation_description=row[16],
                    state=row[17],
                    parent_operation_id=row[18],
                    position_uid=row[19],
                    instrument_uid=row[20],
                    asset_uid=row[21]
                ))
            
            return operations
    
    async def _get_trades_for_operation(self, operation_id: str) -> List[Trade]:
        """Получение сделок для операции из БД"""
        import aiosqlite
        
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute("""
                SELECT * FROM trades WHERE operation_id = ? ORDER BY date_time
            """, (operation_id,)) as cur:
                rows = await cur.fetchall()
                
            trades = []
            for row in rows:
                trades.append(Trade(
                    trade_id=row[0],
                    operation_id=row[1],
                    date_time=datetime.fromisoformat(row[2]),
                    quantity=row[3],
                    price_currency=row[4],
                    price_units=row[5],
                    price_nano=row[6]
                ))
            
            return trades
    
    async def _update_sync_status(self, sync_type: str, last_sync_date: datetime, 
                                last_operation_id: Optional[str], status: str, 
                                error_message: Optional[str] = None) -> None:
        """Обновление статуса синхронизации"""
        import aiosqlite
        
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                INSERT OR REPLACE INTO sync_status (
                    sync_type, last_sync_date, last_operation_id, sync_status,
                    error_message, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                sync_type, last_sync_date.isoformat(), last_operation_id, status,
                error_message, datetime.now().isoformat(), datetime.now().isoformat()
            ))
            await conn.commit()
