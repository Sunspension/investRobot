"""
Сервис синхронизации и восстановления позиций
"""

import asyncio
import aiosqlite
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from robotlib.trading.tinkoff_api_client import TinkoffAPIClient
from robotlib.trading.order_types import OrderDirection
from robotlib.trading.position_sync_interface import PositionSyncServiceable, FIFOEntry, Position
from robotlib.trading.position_restoration_interface import PositionRestorationServiceable
from robotlib.utils.money import Money
from robotlib.utils.logger import get_logger


class PositionSyncService(PositionSyncServiceable):
    """
    Единый сервис для синхронизации и восстановления позиций
    """
    
    def __init__(self, db_path: str, api_client: TinkoffAPIClient, restoration_service: PositionRestorationServiceable):
        self._db_path = db_path
        self._api_client = api_client
        self._logger = get_logger(__name__)
        self._restoration_service = restoration_service
    
    async def sync_positions_on_startup(self, max_retries: int = 3) -> Dict[str, Position]:
        """
        Полная синхронизация позиций при старте с восстановлением FIFO
        
        Args:
            max_retries: Максимальное количество попыток
            
        Returns:
            Словарь позиций {figi: Position}
        """
        self._logger.info("🔄 Полная синхронизация позиций при старте...")
        
        for attempt in range(max_retries):
            try:
                # 1. Получаем позиции из API
                api_positions = await self._get_positions_from_api()
                if not api_positions:
                    self._logger.warning("API не вернул позиции")
                    continue
                
                # 2. Очищаем локальные данные
                await self._clear_local_positions()
                
                # 3. Сохраняем позиции из API
                await self._save_positions_from_api(api_positions)
                
                # 4. Восстанавливаем FIFO из локальных ордеров
                fifo_cache = await self._restore_fifo_from_orders()
                
                # 5. Восстанавливаем FIFO из API, если локальный пустой
                fifo_cache = await self._restoration_service.restore_fifo_from_api(api_positions, fifo_cache)
                
                # 6. Сохраняем операции из API как ордеры в базу данных
                await self._save_api_operations_as_orders(fifo_cache)
                
                # 7. Сохраняем восстановленный FIFO в базу данных
                await self.save_fifo_cache(fifo_cache)
                
                self._logger.info(f"✅ Синхронизация завершена: {len(api_positions)} позиций")
                return api_positions
                
            except Exception as e:
                self._logger.warning(f"⚠️ Попытка {attempt + 1}/{max_retries} не удалась: {e}")
                if attempt == max_retries - 1:
                    self._logger.error(f"❌ Все попытки синхронизации исчерпаны")
                    raise
                await asyncio.sleep(2 ** attempt)
        
        return {}
    
    async def _get_positions_from_api(self) -> Dict[str, Position]:
        """Получает позиции из API"""
        self._logger.info("📡 Получение позиций из API...")
        
        portfolio_response = await self._api_client.get_portfolio()
        if not portfolio_response:
            self._logger.warning("API не вернул портфель")
            return {}
        
        return self._convert_portfolio_response(portfolio_response)
    
    def _convert_portfolio_response(self, portfolio_response) -> Dict[str, Position]:
        """Конвертирует PortfolioResponse в словарь позиций"""
        positions = {}
        try:
            if hasattr(portfolio_response, 'positions') and portfolio_response.positions:
                self._logger.info(f"Найдено {len(portfolio_response.positions)} позиций в ответе портфеля")
                for i, position in enumerate(portfolio_response.positions):
                    try:
                        figi = getattr(position, 'figi', None)
                        quantity = getattr(position, 'quantity', None)
                        if figi is None:
                            self._logger.warning(f"Позиция {i+1}: отсутствует FIGI")
                            continue
                        if quantity is None:
                            self._logger.warning(f"Позиция {i+1} ({figi}): отсутствует количество")
                            continue
                        if quantity == 0:
                            continue
                        # По какой-то причине из API приходят и int и Quotation, поэтому нужно проверять тип
                        if hasattr(quantity, 'units'):
                            quantity_int = quantity.units
                        else:
                            quantity_int = quantity
                        
                        positions[figi] = Position(
                            figi=figi,
                            quantity=quantity_int,
                            avg_price=0.0,
                            last_updated=datetime.now()
                        )
                        self._logger.info(f"✅ Позиция {i+1}: {figi} = {quantity} шт.")
                    except Exception as pos_error:
                        self._logger.error(f"Ошибка обработки позиции {i+1}: {pos_error}")
                        continue
            else:
                self._logger.info("В ответе портфеля нет позиций или поле 'positions' отсутствует")
            self._logger.info(f"Конвертировано {len(positions)} позиций из портфеля")
            return positions
        except Exception as e:
            self._logger.error(f"Ошибка конвертации портфеля: {e}")
            return {}
    
    async def _clear_local_positions(self):
        """Очищает локальные позиции"""
        self._logger.info("🧹 Очистка локальных позиций...")
        
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute("DELETE FROM positions")
            await conn.execute("DELETE FROM position_fifo")
            await conn.commit()
    
    async def _save_positions_from_api(self, api_positions: Dict[str, Position]):
        """Сохраняет позиции из API в локальную БД"""
        self._logger.info(f"💾 Сохранение {len(api_positions)} позиций в БД...")
        
        async with aiosqlite.connect(self._db_path) as conn:
            for figi, position in api_positions.items():
                # avg_price уже типизирован как float в классе Position
                avg_price_float = position.avg_price
                
                await conn.execute("""
                    INSERT OR REPLACE INTO positions (figi, quantity, avg_price, last_updated, api_sync_time)
                    VALUES (?, ?, ?, ?, ?)
                """, (figi, position.quantity, avg_price_float, position.last_updated, datetime.now()))
            await conn.commit()
    
    async def _restore_fifo_from_orders(self) -> Dict[str, List[FIFOEntry]]:
        """Восстанавливает FIFO из истории ордеров"""
        self._logger.info("🔄 Восстановление FIFO из истории ордеров...")
        
        fifo_cache = {}
        
        async with aiosqlite.connect(self._db_path) as conn:
            # Проверяем существование таблицы orders
            async with conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='orders'
            """) as cur:
                table_exists = await cur.fetchone()
            
            if not table_exists:
                self._logger.info("📋 Таблица orders не найдена, пропускаем восстановление FIFO")
                return fifo_cache
            
            # Получаем ордера по FIGI
            async with conn.execute("""
                SELECT figi, quantity, price, time, order_id, direction
                FROM orders 
                WHERE status = 'filled'
                ORDER BY time ASC
            """) as cur:
                rows = await cur.fetchall()
            
            for row in rows:
                figi, quantity, price, timestamp, order_id, direction = row
                if figi not in fifo_cache:
                    fifo_cache[figi] = []
                
                # price из БД уже имеет тип REAL (float)
                price_float = price
                
                fifo_entry = FIFOEntry(
                    quantity=quantity,
                    price=price_float,
                    timestamp=datetime.fromisoformat(timestamp),
                    order_id=order_id,
                    direction=direction or "buy"  # Используем direction из БД или "buy" по умолчанию
                )
                fifo_cache[figi].append(fifo_entry)
            
            # Сохраняем FIFO в БД
            for figi, entries in fifo_cache.items():
                for entry in entries:
                    # Конвертируем price в float используя Money
                    price_float = Money(entry.price).to_float()
                    
                    await conn.execute("""
                        INSERT OR REPLACE INTO position_fifo 
                        (figi, quantity, price, timestamp, order_id, direction)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (figi, entry.quantity, price_float, entry.timestamp, entry.order_id, entry.direction))
            
            await conn.commit()
        
        self._logger.info(f"✅ Восстановлено FIFO для {len(fifo_cache)} FIGI")
        return fifo_cache
    
    async def _save_api_operations_as_orders(self, fifo_cache: Dict[str, List[FIFOEntry]]):
        """Сохраняет операции из API как ордеры в базу данных, проверяя существующие"""
        if not fifo_cache:
            return
            
        self._logger.info("💾 Проверка и сохранение операций из API как ордеры...")
        
        # Используем market.db для таблицы orders
        market_db_path = self._db_path.replace('positions.db', 'market.db')
        async with aiosqlite.connect(market_db_path) as conn:
            total_saved = 0
            total_skipped = 0
            
            for figi, fifo_entries in fifo_cache.items():
                if not fifo_entries:
                    continue
                    
                # Получаем список существующих ордеров для этого FIGI
                existing_orders = set()
                async with conn.execute("""
                    SELECT time, direction, price, quantity FROM orders 
                    WHERE figi = ? AND strategy = 'api_restoration'
                """, (figi,)) as cur:
                    existing_orders = {row async for row in cur}
                
                # Фильтруем только недостающие ордеры
                missing_entries = []
                for entry in fifo_entries:
                    order_key = (
                        entry.timestamp.isoformat(),
                        entry.direction,
                        entry.price,
                        entry.quantity
                    )
                    if order_key not in existing_orders:
                        missing_entries.append(entry)
                
                if not missing_entries:
                    self._logger.info(f"✅ Все ордеры для {figi} уже существуют в базе")
                    total_skipped += len(fifo_entries)
                    continue
                
                # Сохраняем только недостающие ордеры
                for entry in missing_entries:
                    try:
                        await conn.execute("""
                            INSERT INTO orders 
                            (time, figi, direction, price, quantity, reason, strategy)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            entry.timestamp.isoformat(),
                            figi,
                            entry.direction,
                            entry.price,
                            entry.quantity,
                            "Restored from API operations history",  # reason
                            "api_restoration"  # strategy
                        ))
                        total_saved += 1
                    except Exception as e:
                        self._logger.error(f"Ошибка сохранения ордера {entry.order_id}: {e}")
                        continue
                
                self._logger.info(f"✅ {figi}: сохранено {len(missing_entries)} новых ордеров, пропущено {len(fifo_entries) - len(missing_entries)} существующих")
            
            await conn.commit()
        
        self._logger.info(f"✅ Итого: сохранено {total_saved} новых ордеров, пропущено {total_skipped} существующих")
    
    async def get_fifo_cache(self) -> Dict[str, List[FIFOEntry]]:
        """Получает FIFO кэш из БД"""
        fifo_cache = {}
        
        async with aiosqlite.connect(self._db_path) as conn:
            async with conn.execute("""
                SELECT figi, quantity, price, timestamp, order_id, direction
                FROM position_fifo
                ORDER BY timestamp ASC
            """) as cur:
                rows = await cur.fetchall()
            
            for row in rows:
                figi, quantity, price, timestamp, order_id, direction = row
                if figi not in fifo_cache:
                    fifo_cache[figi] = []
                
                # price из БД уже имеет тип REAL (float)
                price_float = price
                
                fifo_entry = FIFOEntry(
                    quantity=quantity,
                    price=price_float,
                    timestamp=datetime.fromisoformat(timestamp),
                    order_id=order_id,
                    direction=direction or "buy"  # Используем direction из БД или "buy" по умолчанию
                )
                fifo_cache[figi].append(fifo_entry)
        
        return fifo_cache
    
    async def save_fifo_cache(self, fifo_cache: Dict[str, List[FIFOEntry]]):
        """Сохраняет FIFO кэш в БД"""
        async with aiosqlite.connect(self._db_path) as conn:
            # Очищаем старые данные
            await conn.execute("DELETE FROM position_fifo")
            
            # Сохраняем новые данные
            for figi, entries in fifo_cache.items():
                for entry in entries:
                    # Конвертируем price в float используя Money
                    price_float = Money(entry.price).to_float()
                    
                    await conn.execute("""
                        INSERT INTO position_fifo 
                        (figi, quantity, price, timestamp, order_id, direction)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (figi, entry.quantity, price_float, entry.timestamp, entry.order_id, entry.direction))
            
            await conn.commit()
