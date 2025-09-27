"""
Сервис для восстановления FIFO данных из API истории операций
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from robotlib.trading.tinkoff_api_client import TinkoffAPIClient
from robotlib.trading.order_types import OrderDirection
from robotlib.trading.position_restoration_interface import (
    PositionRestorationServiceable, 
    FIFOEntry, 
    Position
)
from robotlib.utils.money import Money
from robotlib.utils.logger import get_logger
from tinkoff.invest.schemas import MoneyValue, Operation, Quotation


class PositionRestorationService(PositionRestorationServiceable):
    """
    Сервис для восстановления FIFO данных из API истории операций
    """
    
    @staticmethod
    def _convert_quotation_to_quantity(quantity: int | Quotation) -> int:
        """
        Конвертирует количество в целое число для FIFO записей.
        
        ВАЖНО: Эта функция создана специально для решения проблемы с типами данных
        в Tinkoff API. Несмотря на то, что в SDK Operation.quantity типизирован как int,
        реальный API возвращает Quotation объекты для количеств.
        
        Args:
            quantity: Quotation объект или int с количеством
            
        Returns:
            int: Целое количество лотов для FIFO записи
        """
        if isinstance(quantity, Quotation):
            return quantity.units
        else:
            # Для обычных чисел
            return int(quantity)
    
    def __init__(self, api_client: TinkoffAPIClient, point_value: float = 10.0):
        self._api_client = api_client
        self._logger = get_logger(__name__)
        self._point_value = point_value  # Кешируем point_value
    
    async def restore_fifo_from_api(
        self, 
        api_positions: Dict[str, Position],
        existing_fifo: Dict[str, List[FIFOEntry]],
        days_back: int = 365
    ) -> Dict[str, List[FIFOEntry]]:
        """
        Восстанавливает FIFO данные из API истории операций
        
        Args:
            api_positions: Позиции из API
            existing_fifo: Существующие FIFO данные
            days_back: Количество дней назад для поиска операций
            
        Returns:
            Словарь с восстановленными FIFO данными по FIGI
        """
        self._logger.info("🔄 Начинаем восстановление FIFO из API истории операций...")
        
        restored_fifo = existing_fifo.copy()
        
        for figi, position in api_positions.items():
            # Пропускаем валютные операции (RUB000UTSTOM, USD000UTSTOM и т.д.)
            if figi.endswith('000UTSTOM'):
                self._logger.debug(f"Пропускаем валютную операцию {figi}")
                continue
                
            # Проверяем, есть ли уже FIFO данные для этого FIGI
            if figi in restored_fifo and restored_fifo[figi]:
                self._logger.debug(f"FIFO для {figi} уже существует, пропускаем")
                continue
            
            self._logger.info(f"🔄 Восстановление FIFO для {figi} из API истории операций...")
            
            try:
                # Получаем FIFO записи для этого FIGI
                fifo_entries = await self._get_fifo_entries_for_figi(figi, days_back, api_positions)
                
                if fifo_entries:
                    restored_fifo[figi] = fifo_entries
                    self._logger.info(f"✅ Восстановлено {len(fifo_entries)} FIFO записей для {figi}")
                else:
                    self._logger.warning(f"⚠️ Не удалось восстановить FIFO для {figi}")
                    continue
                    
            except Exception as e:
                self._logger.error(f"❌ Ошибка восстановления FIFO для {figi}: {e}")
                continue
        
        self._logger.info(f"✅ Восстановление FIFO завершено: {len(restored_fifo)} FIGI обработано")
        return restored_fifo
    
    async def _get_fifo_entries_for_figi(
        self, 
        figi: str, 
        days_back: int,
        api_positions: Dict[str, Position]
    ) -> List[FIFOEntry]:
        """
        Получает FIFO записи для конкретного FIGI из API
        
        Args:
            figi: FIGI инструмента
            days_back: Количество дней назад для поиска
            
        Returns:
            Список FIFO записей
        """
        try:
            # Восстанавливаем только те операции, которые сформировали текущую позицию
            current_position = api_positions.get(figi)
            if not current_position:
                self._logger.warning(f"Позиция для {figi} не найдена")
                return []
            
            # Получаем все операции с пагинацией
            all_operations = await self._get_all_operations_with_pagination(figi, days_back)
            
            if not all_operations:
                self._logger.warning(f"Операции для {figi} не найдены")
                return []
            
            fifo_entries = []
            
            # Восстанавливаем все операции, которые сформировали текущую позицию
            for operation in reversed(all_operations):  # Обратный порядок - от новых к старым
                fifo_entry = await self._create_fifo_entry_from_operation(operation)
                if fifo_entry:
                    fifo_entries.append(fifo_entry)
            
            # Сортируем по времени (FIFO порядок)
            fifo_entries.sort(key=lambda x: x.timestamp)
            
            self._logger.info(f"✅ Восстановлено {len(fifo_entries)} FIFO записей для {figi} из {len(all_operations)} операций")
            return fifo_entries
            
        except Exception as e:
            self._logger.error(f"Ошибка получения FIFO для {figi}: {e}")
            return []
    
    async def _get_all_operations_with_pagination(self, figi: str, days_back: int) -> List:
        """
        Получает все операции с пагинацией через курсор
        
        Args:
            figi: FIGI инструмента
            days_back: Количество дней назад для поиска
            
        Returns:
            Список всех операций
        """
        all_operations = []
        cursor = None
        page = 1
        
        # Вычисляем даты для запроса - увеличиваем период для sandbox
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days_back)
        
        # В sandbox режиме делаем несколько запросов с разными периодами
        if hasattr(self._api_client, '_sandbox_token') and self._api_client._sandbox_token:
            # Делаем несколько запросов с разными периодами для получения всех операций
            periods = [
                (to_date - timedelta(days=30), to_date),      # Последние 30 дней
                (to_date - timedelta(days=60), to_date - timedelta(days=30)),  # 30-60 дней назад
                (to_date - timedelta(days=90), to_date - timedelta(days=60)), # 60-90 дней назад
                (to_date - timedelta(days=120), to_date - timedelta(days=90)), # 90-120 дней назад
                (to_date - timedelta(days=180), to_date - timedelta(days=120)), # 120-180 дней назад
                (to_date - timedelta(days=365), to_date - timedelta(days=180)), # 180-365 дней назад
            ]
            
            all_operations = []
            for i, (period_from, period_to) in enumerate(periods):
                self._logger.info(f"🔄 Запрос {i+1}/{len(periods)}: {period_from.date()} - {period_to.date()}")
                
                try:
                    response = await self._api_client.get_operations_by_cursor(
                        from_date=period_from,
                        to_date=period_to,
                        cursor=None,
                        limit=100
                    )
                    
                    if response and hasattr(response, 'operations') and response.operations:
                        figi_operations = [
                            item for item in response.operations 
                            if hasattr(item, 'figi') and item.figi == figi
                        ]
                        all_operations.extend(figi_operations)
                        self._logger.info(f"✅ Период {i+1}: получено {len(figi_operations)} операций для {figi}")
                    else:
                        self._logger.info(f"📋 Период {i+1}: нет операций")
                        
                except Exception as e:
                    self._logger.error(f"Ошибка получения операций для периода {i+1}: {e}")
                    continue
            
            # Подсчитываем итоговый баланс
            total_buy = 0
            total_sell = 0
            for op in all_operations:
                if hasattr(op, 'operation_type') and hasattr(op, 'quantity'):
                    if op.operation_type == 15:  # BUY
                        total_buy += self._convert_quotation_to_quantity(op.quantity)
                    elif op.operation_type == 22:  # SELL
                        total_sell += self._convert_quotation_to_quantity(op.quantity)
            
            net_position = total_buy - total_sell
            self._logger.info(f"✅ Sandbox пагинация завершена: получено {len(all_operations)} операций")
            self._logger.info(f"📊 Итоговый баланс: {total_buy} покупок - {total_sell} продаж = {net_position} лотов")
            return all_operations
        
        self._logger.info(f"🔄 Получение операций для {figi} с пагинацией через курсор: {from_date.date()} - {to_date.date()}")
        
        while True:
            self._logger.debug(f"📡 Запрос страницы {page}, курсор: {cursor[:20] if cursor else 'None'}...")
            
            try:
                # Получаем операции с курсором
                response = await self._api_client.get_operations_by_cursor(
                    from_date=from_date,
                    to_date=to_date,
                    cursor=cursor,
                    limit=100
                )
                
                if not response:
                    self._logger.debug(f"📋 Нет ответа на странице {page}")
                    break
                
                # Обрабатываем разные типы ответов
                if hasattr(response, 'items'):
                    # Ответ с курсором (production)
                    operations = response.items
                    has_next = response.has_next
                    next_cursor = response.next_cursor
                elif hasattr(response, 'operations'):
                    # Обычный ответ (sandbox)
                    operations = response.operations
                    has_next = False  # В sandbox нет пагинации
                    next_cursor = None
                else:
                    self._logger.debug(f"📋 Неизвестный формат ответа на странице {page}")
                    break
                
                if not operations:
                    self._logger.debug(f"📋 Нет операций на странице {page}")
                    break
                
                # Фильтруем операции по FIGI
                figi_operations = [
                    item for item in operations 
                    if hasattr(item, 'figi') and item.figi == figi
                ]
                
                # Логируем детали операций
                if figi_operations:
                    buy_ops = [op for op in figi_operations if hasattr(op, 'operation_type') and op.operation_type == 15]
                    sell_ops = [op for op in figi_operations if hasattr(op, 'operation_type') and op.operation_type == 22]
                    self._logger.debug(f"📊 Страница {page}: {len(buy_ops)} покупок, {len(sell_ops)} продаж для {figi}")
                
                all_operations.extend(figi_operations)
                self._logger.debug(f"✅ Страница {page}: получено {len(figi_operations)} операций для {figi} (всего: {len(all_operations)})")
                
                # Проверяем, есть ли следующая страница
                if not has_next:
                    self._logger.debug(f"📋 Достигнута последняя страница")
                    break
                
                cursor = next_cursor
                page += 1
                
                # Защита от бесконечного цикла
                if page > 100:  # Максимум 100 страниц
                    self._logger.warning(f"⚠️ Достигнут лимит страниц (100), прерываем пагинацию")
                    break
                    
            except Exception as e:
                self._logger.error(f"Ошибка получения операций на странице {page}: {e}")
                break
        
        # Подсчитываем итоговый баланс операций
        total_buy = 0
        total_sell = 0
        for op in all_operations:
            if hasattr(op, 'operation_type') and hasattr(op, 'quantity'):
                if op.operation_type == 15:  # BUY
                    total_buy += self._convert_quotation_to_quantity(op.quantity)
                elif op.operation_type == 22:  # SELL
                    total_sell += self._convert_quotation_to_quantity(op.quantity)
        
        net_position = total_buy - total_sell
        self._logger.info(f"✅ Пагинация завершена: получено {len(all_operations)} операций за {page-1} страниц")
        self._logger.info(f"📊 Итоговый баланс: {total_buy} покупок - {total_sell} продаж = {net_position} лотов")
        return all_operations
    
    async def _create_fifo_entry_from_operation(self, operation: Operation) -> Optional[FIFOEntry]:
        """
        Создает FIFO запись из операции API
        
        Args:
            operation: Операция из API
            
        Returns:
            FIFO запись или None при ошибке
        """
        try:
            # Извлекаем цену из операции
            price = await self._extract_price_from_operation(operation)
            if price <= 0:
                return None
            
            # Определяем направление операции
            direction = self._determine_operation_direction(operation)
            if not direction:
                return None
            
            # Создаем FIFO запись
            fifo_entry = FIFOEntry(
                quantity=self._convert_quotation_to_quantity(operation.quantity),
                price=price,
                timestamp=operation.date,
                order_id=operation.id,
                direction=direction
            )
            
            return fifo_entry
            
        except Exception as e:
            self._logger.error(f"Ошибка создания FIFO записи из операции {operation.id}: {e}")
            return None
    
    async def _extract_price_from_operation(self, operation: Operation) -> float:
        """
        Извлекает цену из операции API
        
        Args:
            operation: Операция из API
            
        Returns:
            Цена операции
        """
        try:
            # Извлекаем цену из операции (фьючерсы всегда в пунктах)
            # Используем кешированный point_value
            point_value = self._point_value
            
            if hasattr(operation, 'price') and operation.price:
                # Для операций всегда применяем point_value для фьючерсов
                return Money(operation.price).to_float() * point_value
            elif hasattr(operation, 'price_units') and hasattr(operation, 'price_nano'):
                # Создаем Money из units и nano, умножаем на point_value для фьючерсов
                return Money(operation.price_units, operation.price_nano).to_float() * point_value
            
            # Если цена не найдена, возвращаем 0
            self._logger.warning(f"Не удалось извлечь цену из операции {operation.id}")
            return 0.0
            
        except Exception as e:
            self._logger.error(f"Ошибка извлечения цены: {e}")
            return 0.0
    
    def _determine_operation_direction(self, operation: Operation) -> Optional[str]:
        """
        Определяет направление операции
        
        Args:
            operation: Операция из API
            
        Returns:
            Направление операции или None
        """
        try:
            # Анализируем тип операции
            operation_type = getattr(operation, 'operation_type', '')
            
            # Определяем направление на основе типа операции
            if operation_type == 15:  # OPERATION_TYPE_BUY
                return "buy"
            elif operation_type == 22:  # OPERATION_TYPE_SELL
                return "sell"
            else:
                self._logger.warning(f"Неизвестный тип операции: {operation_type}")
                return None
                
        except Exception as e:
            self._logger.error(f"Ошибка определения направления операции: {e}")
            return None
    
    async def validate_restored_fifo(
        self, 
        fifo_data: Dict[str, List[FIFOEntry]]
    ) -> Dict[str, bool]:
        """
        Валидирует восстановленные FIFO данные
        
        Args:
            fifo_data: FIFO данные для валидации
            
        Returns:
            Словарь с результатами валидации по FIGI
        """
        validation_results = {}
        
        for figi, fifo_entries in fifo_data.items():
            try:
                # Проверяем базовые условия валидации
                is_valid = True
                
                # 1. Проверяем, что есть записи
                if not fifo_entries:
                    is_valid = False
                    self._logger.warning(f"FIFO для {figi} пустой")
                
                # 2. Проверяем корректность записей
                for entry in fifo_entries:
                    if entry.quantity <= 0:
                        is_valid = False
                        self._logger.warning(f"Некорректное количество в FIFO для {figi}: {entry.quantity}")
                    
                    if entry.price <= 0:
                        is_valid = False
                        self._logger.warning(f"Некорректная цена в FIFO для {figi}: {entry.price}")
                
                # 3. Проверяем сортировку по времени
                timestamps = [entry.timestamp for entry in fifo_entries]
                if timestamps != sorted(timestamps):
                    is_valid = False
                    self._logger.warning(f"FIFO для {figi} не отсортирован по времени")
                
                validation_results[figi] = is_valid
                
                if is_valid:
                    self._logger.info(f"✅ FIFO для {figi} валиден")
                else:
                    self._logger.warning(f"⚠️ FIFO для {figi} содержит ошибки")
                    
            except Exception as e:
                self._logger.error(f"Ошибка валидации FIFO для {figi}: {e}")
                validation_results[figi] = False
        
        return validation_results
