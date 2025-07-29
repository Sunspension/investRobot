#!/usr/bin/env python3
"""
Модуль для управления данными визуализации
Управляет свечами, сигналами, ордерами и их синхронизацией
"""

import random
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd
from robotlib.utils.logger import get_logger

class DataManager:
    """Менеджер данных для визуализации"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
        # Данные для визуализации
        self.candles_data: List[Dict] = []
        self.signals_data: List[Dict] = []
        self.orders_data: List[Dict] = []
        
        # Текущее состояние
        self.current_price: float = 2923.50
        self.last_update: Optional[datetime] = None
        
        # Статистика
        self.buy_count: int = 0
        self.sell_count: int = 0
        self.orders_count: int = 0
        self.total_volume: float = 0.0
        
        # Потокобезопасность
        self.data_lock = threading.Lock()
    
    def add_candle(self, candle_data: Dict[str, Any]) -> None:
        """Добавляет свечу в данные"""
        with self.data_lock:
            self.candles_data.append(candle_data)
            self.current_price = candle_data['close']
            self.last_update = datetime.now()
            
            # Ограничиваем количество свечей
            if len(self.candles_data) > 200:
                self.candles_data = self.candles_data[-100:]
    
    def add_signal(self, signal_data: Dict[str, Any]) -> None:
        """Добавляет сигнал в данные"""
        with self.data_lock:
            self.signals_data.append(signal_data)
            
            if signal_data['type'] == 'buy':
                self.buy_count += 1
            else:
                self.sell_count += 1
            
            # Ограничиваем количество сигналов
            if len(self.signals_data) > 100:
                self.signals_data = self.signals_data[-50:]
    
    def update_orders(self, orders_data: List[Dict[str, Any]]) -> None:
        """Обновляет данные об ордерах"""
        with self.data_lock:
            self.orders_data = orders_data.copy()
            self.orders_count = len(orders_data)
            self.total_volume = sum(order.get('quantity', 1) for order in orders_data)
            
            # Ограничиваем количество ордеров
            if len(self.orders_data) > 100:
                self.orders_data = self.orders_data[-50:]
    
    def get_data_snapshot(self) -> Dict[str, Any]:
        """Возвращает снимок всех данных для безопасного доступа"""
        with self.data_lock:
            return {
                'candles_data': self.candles_data.copy(),
                'signals_data': self.signals_data.copy(),
                'orders_data': self.orders_data.copy(),
                'current_price': self.current_price,
                'last_update': self.last_update,
                'buy_count': self.buy_count,
                'sell_count': self.sell_count,
                'orders_count': self.orders_count,
                'total_volume': self.total_volume
            }
    
    def reset_data(self) -> None:
        """Сбрасывает все данные"""
        with self.data_lock:
            self.candles_data.clear()
            self.signals_data.clear()
            self.orders_data.clear()
            self.buy_count = 0
            self.sell_count = 0
            self.orders_count = 0
            self.total_volume = 0.0
            self.current_price = 2923.50
            self.last_update = None
    
