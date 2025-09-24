#!/usr/bin/env python3
"""
Модуль для управления данными визуализации
Управляет свечами, сигналами, ордерами и их синхронизацией
"""

import threading
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Any

import pandas as pd
import pytz
from visualization.formatters import to_moscow_time
from robotlib.utils.logger import get_logger

class DataManager:
    """Менеджер данных для визуализации"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
        # Данные для визуализации
        self.candles_data: List[Dict] = []
        # Максимальное количество свечей, которое мы держим в памяти (rolling window)
        self.max_candles: int = 5000
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
        
        # Статус рынка
        self.market_status: Dict[str, Any] = {
            'is_trading': False,
            'current_time': None,
            'next_session': None,
            'session_type': 'unknown'
        }
        
        # Статистика сигналов
        self.buy_count: int = 0
        self.sell_count: int = 0
        
        # Статистика ордеров
        self.orders_count: int = 0
        self.buy_orders_count: int = 0
        self.sell_orders_count: int = 0
        
        # Общий объем
        self.total_volume: float = 0.0
        
        # Потокобезопасность
        self.data_lock = threading.Lock()
    
    def add_candle(self, candle_data: Dict[str, Any]) -> None:
        """Добавляет свечу в данные"""
            
        with self.data_lock:
            # Upsert по времени: если бар с таким же временем уже есть, обновляем вместо дублирования
            try:
                t_new = candle_data.get('time')
                if t_new is not None:
                    for i in range(len(self.candles_data) - 1, -1, -1):
                        if self.candles_data[i].get('time') == t_new:
                            self.candles_data[i] = candle_data
                            break
                    else:
                        # Вставляем с сохранением хронологического порядка по времени
                        if not self.candles_data or self.candles_data[-1].get('time') <= t_new:
                            self.candles_data.append(candle_data)
                        else:
                            idx = len(self.candles_data) - 1
                            while idx >= 0 and self.candles_data[idx].get('time') > t_new:
                                idx -= 1
                            self.candles_data.insert(idx + 1, candle_data)
                else:
                    self.candles_data.append(candle_data)
            except Exception:
                # На всякий случай, если что-то пошло не так, просто добавим в конец
                self.candles_data.append(candle_data)
            self.current_price = candle_data['close']
            self.last_update = datetime.now()
            
            # Обновляем общий объем
            self.total_volume += candle_data['volume']
            
            # Ограничиваем количество свечей (оставляем последние max_candles)
            if len(self.candles_data) > self.max_candles:
                overflow = len(self.candles_data) - self.max_candles
                # Удаляем самые старые overflow
                del self.candles_data[0:overflow]
            
            # self.logger.debug(f"Добавлена свеча: {candle_data['time']} @ {candle_data['close']:.2f} (всего: {len(self.candles_data)})")
    
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
            
            self.logger.debug(f"Добавлен сигнал: {signal_data['type']} @ {signal_data.get('price', 0):.2f} (всего: {len(self.signals_data)})")
    
    def add_order(self, order_data: Dict[str, Any]) -> None:
        """Добавляет ордер в данные"""
        with self.data_lock:
            self.orders_data.append(order_data)
            self.orders_count = len(self.orders_data)
            self.total_volume += order_data.get('quantity', 1)
            
            # Подсчитываем ордера по типам
            order_type = order_data.get('type', '').lower()
            if order_type == 'buy':
                self.buy_orders_count += 1
            elif order_type == 'sell':
                self.sell_orders_count += 1
            
            # Ограничиваем количество ордеров
            if len(self.orders_data) > 100:
                self.orders_data = self.orders_data[-50:]
    
    def update_orders(self, orders_data: List[Dict[str, Any]]) -> None:
        """Обновляет данные об ордерах"""
        with self.data_lock:
            self.orders_data = orders_data.copy()
            self.orders_count = len(orders_data)
            self.total_volume = sum(order.get('quantity', 1) for order in orders_data)
            
            # Пересчитываем ордера по типам
            self.buy_orders_count = 0
            self.sell_orders_count = 0
            for order in orders_data:
                order_type = order.get('type', '').lower()
                if order_type == 'buy':
                    self.buy_orders_count += 1
                elif order_type == 'sell':
                    self.sell_orders_count += 1
            
            # Ограничиваем количество ордеров
            if len(self.orders_data) > 100:
                self.orders_data = self.orders_data[-50:]
    
    def update_portfolio(self, portfolio_data: Dict[str, Any]) -> None:
        """Обновляет данные портфеля"""
        with self.data_lock:
            self.portfolio_data.update(portfolio_data)
            self.portfolio_data['last_update'] = datetime.now()
            self.logger.info(
                f"Обновлен портфель: баланс={portfolio_data.get('total_amount', 0):.2f}, "
                f"PnL={portfolio_data.get('pnl', 0):.2f}, позиций={len(self.portfolio_data.get('positions', []))}"
            )
    
    def update_strategy_status(self, status: str) -> None:
        """Обновляет статус стратегий"""
        with self.data_lock:
            self.strategy_status = status
            self.logger.debug(f"Обновлен статус стратегий: {status}")

    def update_market_status(self, status_data: Dict[str, Any]) -> None:
        """Обновляет статус рынка"""
        with self.data_lock:
            self.market_status.update(status_data)
            self.last_update = datetime.now()
            self.logger.info(
                f"Статус рынка: is_trading={self.market_status.get('is_trading')}, "
                f"session={self.market_status.get('session_type')}"
            )
    
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
                'market_status': self.market_status.copy(),
                'strategy_status': self.strategy_status,
                'strategies_data': self.strategies_data.copy(),
                'current_price': self.current_price,
                'last_update': self.last_update,
                'buy_count': self.buy_count,
                'sell_count': self.sell_count,
                'orders_count': self.orders_count,
                'buy_orders_count': self.buy_orders_count,
                'sell_orders_count': self.sell_orders_count,
                'total_volume': self.total_volume
            }
    
    def load_historical_candles(self, db_path: str, figi: str, limit: int = 200) -> None:
        """Загружает исторические свечи из базы данных"""
        try:
            with sqlite3.connect(db_path) as conn:
                # Берём только текущий день (по локальному времени SQLite) и упорядочиваем по времени корректно
                # Нормализуем ISO-время (с 'T') для корректной сортировки/фильтрации в SQLite
                query = """
                SELECT time, open, high, low, close, volume
                FROM candles
                WHERE figi = ?
                  AND date(replace(time, 'T', ' '), 'localtime') = date('now','localtime')
                ORDER BY datetime(replace(time, 'T', ' ')) ASC
                """
                df = pd.read_sql_query(query, conn, params=(figi,))

                if not df.empty:
                    # Конвертируем данные в нужный формат
                    candles = []
                    for _, row in df.iterrows():
                        # Время → naive МСК для стабильного отображения и дальнейшей фильтрации по дню
                        _dt = pd.to_datetime(row['time']).to_pydatetime()
                        candle_data = {
                            'time': to_moscow_time(_dt),
                            'open': float(row['open']),
                            'high': float(row['high']),
                            'low': float(row['low']),
                            'close': float(row['close']),
                            'volume': int(row['volume'])
                        }
                        candles.append(candle_data)
                    # Уже отсортировано по возрастанию и отфильтровано по текущему дню на уровне SQL
                    
                    with self.data_lock:
                        self.candles_data = candles
                        if candles:
                            self.current_price = candles[-1]['close']
                            self.last_update = datetime.now()
                        
                    self.logger.info(f"Загружено {len(candles)} исторических свечей для {figi}")
                else:
                    # Фолбэк: если текущий день пуст (формат времени не распарсен SQLite),
                    # загружаем последние N свечей без фильтра по дате
                    self.logger.debug(
                        f"История за текущий день не найдена, выполняем фолбэк на последние {limit} свечей"
                    )
                    self.load_recent_candles(db_path=db_path, figi=figi, limit=limit)
                    
        except Exception as e:
            self.logger.error(f"Ошибка загрузки исторических данных: {e}")

    def load_recent_candles(self, db_path: str, figi: str, limit: int = 300) -> None:
        """Загружает последние N свечей без ограничения по дате (для первичной инициализации UI).

        Свечи возвращаются в хронологическом порядке (старые → новые).
        """
        try:
            with sqlite3.connect(db_path) as conn:
                query = (
                    "SELECT time, open, high, low, close, volume "
                    "FROM candles WHERE figi = ? "
                    "ORDER BY time DESC LIMIT ?"
                )
                df = pd.read_sql_query(query, conn, params=(figi, limit))

                if not df.empty:
                    # Разворачиваем в возрастающий порядок времени
                    df = df.iloc[::-1].reset_index(drop=True)

                    candles = []
                    for _, row in df.iterrows():
                        _dt = pd.to_datetime(row['time']).to_pydatetime()
                        candle_data = {
                            'time': to_moscow_time(_dt),
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
                    self.logger.info(f"Загружено {len(candles)} последних свечей для {figi}")
                else:
                    self.logger.warning(f"Свечи для {figi} не найдены в {db_path}")
        except Exception as e:
            self.logger.error(f"Ошибка загрузки последних свечей: {e}")

    def merge_historical_candles(self, db_path: str, figi: str, from_time: datetime, to_time: Optional[datetime] = None) -> None:
        """Догружает и сливает свечи из БД в заданном окне времени, не перезаписывая весь список.

        Использует upsert по времени (add_candle), чтобы заполнить пропуски после разрывов стрима.
        """
        try:
            import sqlite3
            import pandas as pd
            from visualization.formatters import to_moscow_time
            import pytz
            from datetime import timezone as _tz

            def _as_utc_sqlstr(dt: datetime) -> str:
                """Возвращает UTC-дату в ISO8601 с оффсетом (+00:00) для корректного сравнения в SQLite."""
                if dt.tzinfo is None:
                    msk = pytz.timezone('Europe/Moscow')
                    dt = msk.localize(dt)
                return dt.astimezone(_tz.utc).isoformat()

            params = [figi, _as_utc_sqlstr(from_time)]
            to_clause = ""
            if to_time is not None:
                to_clause = " AND time <= ?"
                params.append(_as_utc_sqlstr(to_time))

            query = (
                "SELECT time, open, high, low, close, volume FROM candles "
                "WHERE figi = ? AND datetime(time) >= datetime(?)" + to_clause.replace("time", "datetime(time)") + " ORDER BY datetime(time) ASC"
            )
            with sqlite3.connect(db_path) as conn:
                df = pd.read_sql_query(query, conn, params=params)
                if df.empty:
                    return
                for _, row in df.iterrows():
                    dt_val = pd.to_datetime(row['time']).to_pydatetime()
                    candle_data = {
                        'time': to_moscow_time(dt_val),
                        'open': float(row['open']),
                        'high': float(row['high']),
                        'low': float(row['low']),
                        'close': float(row['close']),
                        'volume': int(row['volume'])
                    }
                    self.add_candle(candle_data)
        except Exception as e:
            self.logger.error(f"Ошибка merge_historical_candles: {e}")
    
    def reset_data(self) -> None:
        """Сбрасывает все данные"""
        with self.data_lock:
            self.candles_data.clear()
            self.signals_data.clear()
            self.orders_data.clear()
            self.buy_count = 0
            self.sell_count = 0
            self.orders_count = 0
            self.buy_orders_count = 0
            self.sell_orders_count = 0
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
    
