"""
Сервис статистики и отчетов на основе данных из БД
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import aiosqlite

from robotlib.utils.logger import get_logger


@dataclass
class TradingStats:
    """Статистика торговли"""
    total_orders: int
    buy_orders: int
    sell_orders: int
    total_volume: int
    total_turnover: float
    total_commission: float
    avg_price: float
    profit_loss: float
    win_rate: float
    max_profit: float
    max_loss: float


@dataclass
class PositionStats:
    """Статистика позиций"""
    figi: str
    current_position: int
    avg_buy_price: float
    avg_sell_price: float
    unrealized_pnl: float
    realized_pnl: float
    total_trades: int


@dataclass
class PeriodReport:
    """Отчет за период"""
    period_start: datetime
    period_end: datetime
    trading_stats: TradingStats
    position_stats: List[PositionStats]
    daily_stats: List[Dict[str, Any]]


class StatisticsService:
    """Сервис статистики и отчетов"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = get_logger(__name__)
    
    async def get_trading_stats(self, start_date: datetime, end_date: datetime, 
                              figi: Optional[str] = None) -> TradingStats:
        """Получение статистики торговли за период"""
        
        # Базовый запрос
        base_query = """
            SELECT 
                COUNT(*) as total_orders,
                SUM(CASE WHEN direction = 'buy' THEN 1 ELSE 0 END) as buy_orders,
                SUM(CASE WHEN direction = 'sell' THEN 1 ELSE 0 END) as sell_orders,
                SUM(quantity) as total_volume,
                SUM(price * quantity) as total_turnover,
                SUM(commission) as total_commission,
                AVG(price) as avg_price
            FROM orders 
            WHERE time BETWEEN ? AND ?
        """
        
        params = [start_date.isoformat(), end_date.isoformat()]
        
        if figi:
            base_query += " AND figi = ?"
            params.append(figi)
        
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute(base_query, params) as cur:
                row = await cur.fetchone()
            
            if not row or row[0] == 0:
                return TradingStats(0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            
            total_orders, buy_orders, sell_orders, total_volume, total_turnover, total_commission, avg_price = row
            
            # Вычисляем P&L
            pnl_query = """
                SELECT 
                    SUM(CASE WHEN direction = 'sell' THEN price * quantity ELSE 0 END) as sell_turnover,
                    SUM(CASE WHEN direction = 'buy' THEN price * quantity ELSE 0 END) as buy_turnover
                FROM orders 
                WHERE time BETWEEN ? AND ?
            """
            
            if figi:
                pnl_query += " AND figi = ?"
            
            async with conn.execute(pnl_query, params) as cur:
                pnl_row = await cur.fetchone()
            
            sell_turnover = pnl_row[0] or 0
            buy_turnover = pnl_row[1] or 0
            profit_loss = sell_turnover - buy_turnover - total_commission
            
            # Вычисляем win rate
            win_rate = 0.0
            if total_orders > 0:
                # Простая логика: считаем прибыльными сделки с положительным P&L
                # В реальности нужно более сложная логика
                win_rate = 0.5  # Заглушка
            
            return TradingStats(
                total_orders=total_orders,
                buy_orders=buy_orders,
                sell_orders=sell_orders,
                total_volume=total_volume,
                total_turnover=total_turnover,
                total_commission=total_commission,
                avg_price=avg_price,
                profit_loss=profit_loss,
                win_rate=win_rate,
                max_profit=0.0,  # Нужно вычислять отдельно
                max_loss=0.0     # Нужно вычислять отдельно
            )
    
    async def get_position_stats(self, figi: str, as_of_date: Optional[datetime] = None) -> PositionStats:
        """Получение статистики позиции по инструменту"""
        
        if as_of_date is None:
            as_of_date = datetime.now()
        
        async with aiosqlite.connect(self.db_path) as conn:
            # Текущая позиция
            position_query = """
                SELECT 
                    SUM(CASE WHEN direction = 'buy' THEN quantity ELSE -quantity END) as current_position,
                    AVG(CASE WHEN direction = 'buy' THEN price END) as avg_buy_price,
                    AVG(CASE WHEN direction = 'sell' THEN price END) as avg_sell_price,
                    COUNT(*) as total_trades
                FROM orders 
                WHERE figi = ? AND time <= ?
            """
            
            async with conn.execute(position_query, [figi, as_of_date.isoformat()]) as cur:
                row = await cur.fetchone()
            
            if not row:
                return PositionStats(figi, 0, 0.0, 0.0, 0.0, 0.0, 0)
            
            current_position, avg_buy_price, avg_sell_price, total_trades = row
            
            # Вычисляем реализованный P&L
            realized_pnl_query = """
                SELECT 
                    SUM(CASE WHEN direction = 'sell' THEN price * quantity ELSE 0 END) as sell_turnover,
                    SUM(CASE WHEN direction = 'buy' THEN price * quantity ELSE 0 END) as buy_turnover,
                    SUM(commission) as total_commission
                FROM orders 
                WHERE figi = ? AND time <= ?
            """
            
            async with conn.execute(realized_pnl_query, [figi, as_of_date.isoformat()]) as cur:
                pnl_row = await cur.fetchone()
            
            sell_turnover = pnl_row[0] or 0
            buy_turnover = pnl_row[1] or 0
            total_commission = pnl_row[2] or 0
            realized_pnl = sell_turnover - buy_turnover - total_commission
            
            # Нереализованный P&L (нужно получить текущую цену)
            unrealized_pnl = 0.0  # Заглушка - нужно получать текущую цену из API
            
            return PositionStats(
                figi=figi,
                current_position=current_position or 0,
                avg_buy_price=avg_buy_price or 0.0,
                avg_sell_price=avg_sell_price or 0.0,
                unrealized_pnl=unrealized_pnl,
                realized_pnl=realized_pnl,
                total_trades=total_trades or 0
            )
    
    async def get_period_report(self, start_date: datetime, end_date: datetime) -> PeriodReport:
        """Получение полного отчета за период"""
        
        # Общая статистика
        trading_stats = await self.get_trading_stats(start_date, end_date)
        
        # Статистика по позициям
        position_stats = []
        
        # Получаем все уникальные FIGI за период
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute("""
                SELECT DISTINCT figi FROM orders 
                WHERE time BETWEEN ? AND ?
            """, [start_date.isoformat(), end_date.isoformat()]) as cur:
                figis = [row[0] async for row in cur]
        
        for figi in figis:
            position_stat = await self.get_position_stats(figi, end_date)
            position_stats.append(position_stat)
        
        # Дневная статистика
        daily_stats = await self.get_daily_stats(start_date, end_date)
        
        return PeriodReport(
            period_start=start_date,
            period_end=end_date,
            trading_stats=trading_stats,
            position_stats=position_stats,
            daily_stats=daily_stats
        )
    
    async def get_daily_stats(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Получение дневной статистики"""
        
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute("""
                SELECT 
                    DATE(time) as date,
                    COUNT(*) as orders_count,
                    SUM(quantity) as volume,
                    SUM(price * quantity) as turnover,
                    SUM(commission) as commission,
                    SUM(CASE WHEN direction = 'buy' THEN price * quantity ELSE 0 END) as buy_turnover,
                    SUM(CASE WHEN direction = 'sell' THEN price * quantity ELSE 0 END) as sell_turnover
                FROM orders 
                WHERE time BETWEEN ? AND ?
                GROUP BY DATE(time)
                ORDER BY date
            """, [start_date.isoformat(), end_date.isoformat()]) as cur:
                rows = await cur.fetchall()
            
            daily_stats = []
            for row in rows:
                date, orders_count, volume, turnover, commission, buy_turnover, sell_turnover = row
                daily_pnl = sell_turnover - buy_turnover - commission
                
                daily_stats.append({
                    "date": date,
                    "orders_count": orders_count,
                    "volume": volume,
                    "turnover": turnover,
                    "commission": commission,
                    "buy_turnover": buy_turnover,
                    "sell_turnover": sell_turnover,
                    "daily_pnl": daily_pnl
                })
            
            return daily_stats
    
    async def get_variation_margin(self, figi: str, current_price: float) -> Dict[str, Any]:
        """Вычисление вариационной маржи"""
        
        position_stats = await self.get_position_stats(figi)
        
        if position_stats.current_position == 0:
            return {
                "figi": figi,
                "position": 0,
                "variation_margin": 0.0,
                "unrealized_pnl": 0.0
            }
        
        # Вариационная маржа = (текущая цена - средняя цена) * количество
        if position_stats.current_position > 0:  # Длинная позиция
            avg_price = position_stats.avg_buy_price
            variation_margin = (current_price - avg_price) * position_stats.current_position
        else:  # Короткая позиция
            avg_price = position_stats.avg_sell_price
            variation_margin = (avg_price - current_price) * abs(position_stats.current_position)
        
        return {
            "figi": figi,
            "position": position_stats.current_position,
            "avg_price": avg_price,
            "current_price": current_price,
            "variation_margin": variation_margin,
            "unrealized_pnl": variation_margin,
            "realized_pnl": position_stats.realized_pnl
        }
    
    async def export_report(self, start_date: datetime, end_date: datetime, 
                          format: str = "json") -> str:
        """Экспорт отчета в различных форматах"""
        
        report = await self.get_period_report(start_date, end_date)
        
        if format == "json":
            import json
            return json.dumps({
                "period_start": report.period_start.isoformat(),
                "period_end": report.period_end.isoformat(),
                "trading_stats": {
                    "total_orders": report.trading_stats.total_orders,
                    "buy_orders": report.trading_stats.buy_orders,
                    "sell_orders": report.trading_stats.sell_orders,
                    "total_volume": report.trading_stats.total_volume,
                    "total_turnover": report.trading_stats.total_turnover,
                    "total_commission": report.trading_stats.total_commission,
                    "avg_price": report.trading_stats.avg_price,
                    "profit_loss": report.trading_stats.profit_loss,
                    "win_rate": report.trading_stats.win_rate
                },
                "position_stats": [
                    {
                        "figi": pos.figi,
                        "current_position": pos.current_position,
                        "avg_buy_price": pos.avg_buy_price,
                        "avg_sell_price": pos.avg_sell_price,
                        "unrealized_pnl": pos.unrealized_pnl,
                        "realized_pnl": pos.realized_pnl,
                        "total_trades": pos.total_trades
                    }
                    for pos in report.position_stats
                ],
                "daily_stats": report.daily_stats
            }, indent=2, ensure_ascii=False)
        
        elif format == "csv":
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Заголовки
            writer.writerow(["Date", "Orders", "Volume", "Turnover", "Commission", "Daily P&L"])
            
            # Данные
            for daily in report.daily_stats:
                writer.writerow([
                    daily["date"],
                    daily["orders_count"],
                    daily["volume"],
                    daily["turnover"],
                    daily["commission"],
                    daily["daily_pnl"]
                ])
            
            return output.getvalue()
        
        else:
            raise ValueError(f"Неподдерживаемый формат: {format}")
