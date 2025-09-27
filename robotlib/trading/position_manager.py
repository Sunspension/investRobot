"""
Менеджер позиций с FIFO логикой для торговых стратегий
"""

import asyncio
import aiosqlite
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass

from robotlib.trading.interfaces import PositionManageable
from robotlib.trading.position_sync_interface import PositionSyncServiceable, FIFOEntry, Position
from robotlib.utils.logger import get_logger


@dataclass
class LossPosition:
    """Убыточная позиция"""
    quantity: int
    price: float
    loss_percent: float
    order_id: str


@dataclass
class ProfitPosition:
    """Прибыльная позиция"""
    quantity: int
    price: float
    profit_percent: float
    order_id: str


class PositionManager(PositionManageable):
    """Менеджер позиций с FIFO логикой"""
    
    def __init__(
        self, 
        db_path: str, 
        risk_manager,
        sync_service: PositionSyncServiceable
    ):
        self._db_path = db_path
        self._risk_manager = risk_manager
        self._sync_service = sync_service
        self._logger = get_logger(__name__)
        self._positions_cache: Dict[str, Position] = {}
        self._fifo_cache: Dict[str, List[FIFOEntry]] = {}
        self._last_sync_time: Optional[datetime] = None
    
    async def sync_on_startup(self, max_retries: int = 3) -> Dict[str, Position]:
        """Синхронизация позиций при старте с повторными попытками"""
        self._logger.info("🔄 Синхронизация позиций при старте...")
        
        # Делегируем всю логику синхронизации сервису
        api_positions = await self._sync_service.sync_positions_on_startup(max_retries)
        
        # Получаем FIFO кэш из сервиса
        self._fifo_cache = await self._sync_service.get_fifo_cache()
        
        # Обновляем кэш
        self._positions_cache = api_positions
        self._last_sync_time = datetime.now()
        
        self._logger.info(f"✅ Синхронизация завершена: {len(api_positions)} позиций")
        return api_positions
    
    
    def get_position(self, figi: str) -> Optional[Position]:
        """Получение позиции из кэша"""
        return self._positions_cache.get(figi)
    
    async def get_position_direction(self, figi: str) -> Optional[str]:
        """Получение направления позиции для инструмента"""
        fifo_queue = await self.get_current_fifo_queue(figi)
        if not fifo_queue:
            return None
        
        # Возвращаем направление первой записи (все должны быть одинаковыми)
        return fifo_queue[0].direction
    
    async def get_current_fifo_queue(self, figi: str) -> List[FIFOEntry]:
        """Получение текущей FIFO очереди для позиции"""
        if figi in self._fifo_cache:
            return self._fifo_cache[figi]
        
        # Загружаем из БД
        async with aiosqlite.connect(self._db_path) as conn:
            async with conn.execute("""
                SELECT quantity, price, timestamp, order_id, direction
                FROM position_fifo 
                WHERE figi = ? 
                ORDER BY timestamp
            """, (figi,)) as cur:
                rows = await cur.fetchall()
        
        fifo_queue = []
        for row in rows:
            fifo_queue.append(FIFOEntry(
                quantity=row[0],
                price=row[1],
                timestamp=datetime.fromisoformat(row[2]),
                order_id=row[3],
                direction=row[4]
            ))
        
        self._fifo_cache[figi] = fifo_queue
        return fifo_queue
    
    async def get_loss_positions(
        self, 
        figi: str, 
        current_price: float, 
        loss_threshold: float = None
    ) -> List[LossPosition]:
        """Получение убыточных позиций по FIFO
        
        Args:
            figi: FIGI инструмента
            current_price: Текущая цена
            loss_threshold: Порог убытка в пунктах (не в процентах!). Если None, берется из risk_manager
        """
        if loss_threshold is None:
            loss_threshold = self._risk_manager.risk_limits.stop_loss_threshold
        fifo_queue = await self.get_current_fifo_queue(figi)
        
        if not fifo_queue:
            return []
        
        # Определяем тип позиции по первой записи (все записи должны быть одного типа)
        position_direction = fifo_queue[0].direction
        
        # Проверяем консистентность направления
        for entry in fifo_queue:
            if entry.direction != position_direction:
                self._logger.warning(f"⚠️ Обнаружены смешанные позиции для {figi}: {position_direction} и {entry.direction}")
                # Продолжаем с основным направлением
        
        loss_positions = []
        for entry in fifo_queue:
            if position_direction == 'long':
                # Для лонга: убыток = цена покупки - текущая цена
                loss_points = entry.price - current_price
            else:  # short
                # Для шорта: убыток = текущая цена - цена продажи
                loss_points = current_price - entry.price
            
            # Проверяем, что это действительно убыток (loss_points > 0) и он превышает порог
            if loss_points > 0 and loss_points >= loss_threshold:
                loss_percent = loss_points / entry.price  # Процент для отображения
                loss_positions.append(LossPosition(
                    quantity=entry.quantity,
                    price=entry.price,
                    loss_percent=loss_percent,
                    order_id=entry.order_id
                ))
        
        return loss_positions
    
    async def get_profit_positions(
        self, 
        figi: str, 
        current_price: float
    ) -> List[ProfitPosition]:
        """Получение прибыльных позиций по FIFO"""
        fifo_queue = await self.get_current_fifo_queue(figi)
        
        if not fifo_queue:
            return []
        
        # Определяем тип позиции по первой записи (все записи должны быть одного типа)
        position_direction = fifo_queue[0].direction
        
        # Проверяем консистентность направления
        for entry in fifo_queue:
            if entry.direction != position_direction:
                self._logger.warning(f"⚠️ Обнаружены смешанные позиции для {figi}: {position_direction} и {entry.direction}")
                # Продолжаем с основным направлением
        
        profit_positions = []
        for entry in fifo_queue:
            if position_direction == 'long':
                # Для лонга: прибыль = текущая цена - цена покупки
                profit_points = current_price - entry.price
            else:  # short
                # Для шорта: прибыль = цена продажи - текущая цена
                profit_points = entry.price - current_price
            
            if profit_points > 0:
                profit_percent = profit_points / entry.price
                profit_positions.append(ProfitPosition(
                    quantity=entry.quantity,
                    price=entry.price,
                    profit_percent=profit_percent,
                    order_id=entry.order_id
                ))
        
        return profit_positions
    
    async def add_to_fifo(
        self, 
        figi: str, 
        quantity: int, 
        price: float, 
        order_id: str,
        direction: str = 'long'  # 'long' или 'short'
    ):
        """Добавление позиции в FIFO очередь"""
        # Проверяем, есть ли уже позиции для этого инструмента
        existing_direction = await self.get_position_direction(figi)
        if existing_direction and existing_direction != direction:
            self._logger.error(f"❌ Попытка добавить {direction} позицию для {figi}, но уже есть {existing_direction} позиции!")
            self._logger.error(f"   Для одного инструмента не может быть одновременно лонг и шорт позиций!")
            raise ValueError(f"Нельзя смешивать {direction} и {existing_direction} позиции для {figi}")
        
        entry = FIFOEntry(
            quantity=quantity,
            price=price,
            timestamp=datetime.now(),
            order_id=order_id,
            direction=direction
        )
        
        # Добавляем в кэш
        if figi not in self._fifo_cache:
            self._fifo_cache[figi] = []
        self._fifo_cache[figi].append(entry)
        
        # Сохраняем в БД
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute("""
                INSERT INTO position_fifo (figi, quantity, price, timestamp, order_id, direction)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (figi, quantity, price, entry.timestamp.isoformat(), order_id, "buy"))
            await conn.commit()
        
        # Обновляем кэш позиций
        await self._update_position_cache(figi)
    
    async def _update_position_cache(self, figi: str):
        """Обновление кэша позиций для конкретного инструмента"""
        fifo_queue = await self.get_current_fifo_queue(figi)
        if not fifo_queue:
            # Нет позиций - удаляем из кэша
            if figi in self._positions_cache:
                del self._positions_cache[figi]
            return
        
        # Подсчитываем общую позицию
        total_quantity = sum(entry.quantity for entry in fifo_queue)
        if total_quantity == 0:
            # Позиция закрыта
            if figi in self._positions_cache:
                del self._positions_cache[figi]
            return
        
        # Рассчитываем среднюю цену
        total_value = sum(entry.quantity * entry.price for entry in fifo_queue)
        avg_price = total_value / total_quantity if total_quantity > 0 else 0.0
        
        # Обновляем кэш
        self._positions_cache[figi] = Position(
            figi=figi,
            quantity=total_quantity,
            avg_price=avg_price,
            last_updated=datetime.now()
        )
    
    async def remove_from_fifo(
        self, 
        figi: str, 
        quantity: int
    ):
        """Удаление позиций из FIFO очереди по принципу FIFO"""
        if figi not in self._fifo_cache:
            return
        
        remaining_quantity = quantity
        fifo_queue = self._fifo_cache[figi]
        
        # Удаляем по принципу FIFO
        while remaining_quantity > 0 and fifo_queue:
            entry = fifo_queue[0]
            
            if entry.quantity <= remaining_quantity:
                # Удаляем всю запись
                remaining_quantity -= entry.quantity
                fifo_queue.pop(0)
            else:
                # Уменьшаем количество в записи
                entry.quantity -= remaining_quantity
                remaining_quantity = 0
        
        # Обновляем БД
        await self._update_fifo_in_db(figi, fifo_queue)
    
    async def update_position_after_trade(
        self, 
        figi: str, 
        quantity_delta: int, 
        price: float
    ):
        """Обновление позиции после сделки"""
        if figi in self._positions_cache:
            current = self._positions_cache[figi]
            new_quantity = current.quantity + quantity_delta
            
            if new_quantity == 0:
                # Позиция закрыта
                del self._positions_cache[figi]
            else:
                # Обновляем позицию
                new_avg_price = self._calculate_avg_price(
                    current.quantity, current.avg_price,
                    quantity_delta, price
                )
                
                self._positions_cache[figi] = Position(
                    figi=figi,
                    quantity=new_quantity,
                    avg_price=new_avg_price,
                    last_updated=datetime.now()
                )
    
    def _calculate_avg_price(self, current_qty: int, current_avg: float, 
                           delta_qty: int, delta_price: float) -> float:
        """Вычисление средней цены после сделки"""
        if current_qty + delta_qty == 0:
            return 0.0
        
        total_cost = (current_qty * current_avg) + (delta_qty * delta_price)
        return total_cost / (current_qty + delta_qty)
    
    
    
    async def _remove_from_fifo_queue(
        self, 
        figi: str, 
        sell_quantity: int, 
        fifo_queue: List[Dict]
    ):
        """Удаление позиций из FIFO очереди при продаже"""
        remaining_sell = sell_quantity
        
        while remaining_sell > 0 and fifo_queue:
            entry = fifo_queue[0]
            entry_quantity = entry['quantity']
            
            if entry_quantity <= remaining_sell:
                # Удаляем всю запись
                fifo_queue.pop(0)
                remaining_sell -= entry_quantity
            else:
                # Уменьшаем количество в записи
                entry['quantity'] -= remaining_sell
                remaining_sell = 0
    
    async def _update_fifo_in_db(
        self, 
        figi: str, 
        fifo_queue: List[FIFOEntry]
    ):
        """Обновление FIFO очереди в БД"""
        async with aiosqlite.connect(self._db_path) as conn:
            # Удаляем старые записи
            await conn.execute("DELETE FROM position_fifo WHERE figi = ?", (figi,))
            
            # Добавляем новые записи
            for entry in fifo_queue:
                # entry.price уже типизирован как float в FIFOEntry
                price_float = entry.price
                
                await conn.execute("""
                    INSERT INTO position_fifo (figi, quantity, price, timestamp, order_id, direction)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    figi, entry.quantity, price_float, 
                    entry.timestamp.isoformat(), entry.order_id, entry.direction
                ))
            await conn.commit()
    
    async def get_stop_loss_positions(self, current_price: float, loss_threshold: float) -> Dict[str, List[LossPosition]]:
        """Возвращает убыточные позиции для всех инструментов
        
        Args:
            current_price: Текущая цена
            loss_threshold: Порог убытка в пунктах
            
        Returns:
            Словарь {figi: [LossPosition, ...]} с убыточными позициями
        """
        result = {}
        
        # Получаем все FIGI с позициями
        all_figis = await self._get_all_figis()
        
        self._logger.debug(f"🛡️ Получение убыточных позиций для {len(all_figis)} инструментов при цене {current_price}")
        
        for figi in all_figis:
            self._logger.debug(f"  Проверяем убыточные позиции для {figi}")
            
            loss_positions = await self.get_loss_positions(figi, current_price, loss_threshold)
            
            if loss_positions:
                result[figi] = loss_positions
                self._logger.debug(f"    ✅ Найдено {len(loss_positions)} убыточных позиций для {figi}")
            else:
                self._logger.debug(f"    ❌ Убыточных позиций нет для {figi}")
        
        return result
    
    async def _get_all_figis(self) -> List[str]:
        """Получает все FIGI с позициями"""
        async with aiosqlite.connect(self._db_path) as conn:
            cursor = await conn.execute("""
                SELECT DISTINCT figi FROM position_fifo
            """)
            rows = await cursor.fetchall()
            return [row[0] for row in rows]
    
