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
        
        # Данные портфеля
        self.portfolio_data: Dict[str, Any] = {
            'total_amount': 0.0,
            'positions': [],
            'pnl': 0.0,
            'margin': 0.0,
            'free_margin': 0.0,
            'last_update': None
        }
        
        # Статус стратегий
        self.strategy_status: str = "Инициализация..."
        self.strategies_data: List[Dict[str, Any]] = []
        
        # Текущее состояние
        self.current_price: float = 0.0
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
    
    def add_order(self, order_data: Dict[str, Any]) -> None:
        """Добавляет ордер в данные"""
        with self.data_lock:
            self.orders_data.append(order_data)
            self.orders_count = len(self.orders_data)
            self.total_volume += order_data.get('quantity', 1)
            
            # Ограничиваем количество ордеров
            if len(self.orders_data) > 100:
                self.orders_data = self.orders_data[-50:]
    
    def update_orders(self, orders_data: List[Dict[str, Any]]) -> None:
        """Обновляет данные об ордерах"""
        with self.data_lock:
            self.orders_data = orders_data.copy()
            self.orders_count = len(orders_data)
            self.total_volume = sum(order.get('quantity', 1) for order in orders_data)
            
            # Ограничиваем количество ордеров
            if len(self.orders_data) > 100:
                self.orders_data = self.orders_data[-50:]
    
    def update_portfolio(self, portfolio_data: Dict[str, Any]) -> None:
        """Обновляет данные портфеля"""
        with self.data_lock:
            self.portfolio_data.update(portfolio_data)
            self.portfolio_data['last_update'] = datetime.now()
            self.logger.debug(f"Обновлен портфель: баланс={portfolio_data.get('total_amount', 0):.2f}, PnL={portfolio_data.get('pnl', 0):.2f}")
    
    def update_strategy_status(self, status: str) -> None:
        """Обновляет статус стратегий"""
        with self.data_lock:
            self.strategy_status = status
            self.logger.debug(f"Обновлен статус стратегий: {status}")
    
    def update_strategies_data(self, strategies_data: List[Dict[str, Any]]) -> None:
        """Обновляет данные о стратегиях"""
        with self.data_lock:
            self.strategies_data = strategies_data
            self.logger.debug(f"Обновлены данные стратегий: {len(strategies_data)} стратегий")
    
    def get_data_snapshot(self) -> Dict[str, Any]:
        """Возвращает снимок всех данных для безопасного доступа"""
        with self.data_lock:
            return {
                'candles_data': self.candles_data.copy(),
                'signals_data': self.signals_data.copy(),
                'orders_data': self.orders_data.copy(),
                'portfolio_data': self.portfolio_data.copy(),
                'strategy_status': self.strategy_status,
                'strategies_data': self.strategies_data.copy(),
                'current_price': self.current_price,
                'last_update': self.last_update,
                'buy_count': self.buy_count,
                'sell_count': self.sell_count,
                'orders_count': self.orders_count,
                'total_volume': self.total_volume
            }
    
    def load_historical_candles(self, db_path: str, figi: str, limit: int = 200) -> None:
        """Загружает исторические свечи из базы данных"""
        try:
            import sqlite3
            import pandas as pd
            
            with sqlite3.connect(db_path) as conn:
                query = """
                SELECT time, open, high, low, close, volume
                FROM candles 
                WHERE figi = ? 
                ORDER BY time DESC 
                LIMIT ?
                """
                df = pd.read_sql_query(query, conn, params=(figi, limit))
                
                if not df.empty:
                    # Конвертируем данные в нужный формат
                    candles = []
                    for _, row in df.iterrows():
                        candle_data = {
                            'time': pd.to_datetime(row['time']),
                            'open': float(row['open']),
                            'high': float(row['high']),
                            'low': float(row['low']),
                            'close': float(row['close']),
                            'volume': int(row['volume'])
                        }
                        candles.append(candle_data)
                    
                    with self.data_lock:
                        self.candles_data = candles
                        if candles:
                            self.current_price = candles[-1]['close']
                            self.last_update = datetime.now()
                        
                    self.logger.info(f"Загружено {len(candles)} исторических свечей для {figi}")
                else:
                    self.logger.warning(f"Исторические данные для {figi} не найдены")
                    
        except Exception as e:
            self.logger.error(f"Ошибка загрузки исторических данных: {e}")
    
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
            self.current_price = 0.0
            self.last_update = None
            
            # Сбрасываем данные портфеля
            self.portfolio_data = {
                'total_amount': 0.0,
                'positions': [],
                'pnl': 0.0,
                'margin': 0.0,
                'free_margin': 0.0,
                'last_update': None
            }
            
            # Сбрасываем статус стратегий
            self.strategy_status = "Сброшено"
            self.strategies_data = []
            
            self.logger.info("Все данные визуализации сброшены")
    
