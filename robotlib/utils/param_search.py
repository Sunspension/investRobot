from __future__ import annotations

import itertools
import asyncio
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Dict, Any

from robotlib.signal_manager import SignalManager
from robotlib.strategies.strategy_manager import StrategyManager
from robotlib.strategies.long import LongStrategy
from robotlib.strategies.short import ShortStrategy
from robotlib.utils.backtest_sqlite import run_backtest_from_sqlite
from robotlib.trading.risk_manager import RiskLimits
from unittest.mock import Mock


@dataclass
class SearchSpace:
    macd_fast: list[int]
    macd_slow: list[int]
    macd_signal: list[int]
    atr_period: list[int]
    lookback_min: list[int]
    lookback_max: list[int]
    peak_prominence: list[float]


def iter_param_combinations(space: SearchSpace):
    keys = [
        "macd_fast",
        "macd_slow",
        "macd_signal",
        "atr_period",
        "lookback_min",
        "lookback_max",
        "peak_prominence",
    ]
    for values in itertools.product(*[getattr(space, k) for k in keys]):
        yield dict(zip(keys, values))


async def maximize_income(
    db_path: str,
    figi: str,
    from_time: datetime,
    to_time: datetime,
    search_space: SearchSpace,
    deposit: int = 400000,
    percent_from_deposit: int = 50,
    items_per_trade: int = 20,
    max_combinations: int = None,
) -> dict:
    """
    Перебирает пространство параметров SignalManager и возвращает лучшую конфигурацию по доходу.
    """
    best = {"income": float("-inf"), "params": None}
    
    # Вычисляем количество дней для расчета дневной доходности
    days = (to_time - from_time).days + 1
    if days == 0:
        days = 1  # минимум 1 день для расчета

    total_combinations = 1
    for key in ["macd_fast", "macd_slow", "macd_signal", "atr_period", "lookback_min", "lookback_max", "peak_prominence"]:
        total_combinations *= len(getattr(search_space, key))
    
    print(f"Начинаем оптимизацию: {total_combinations} комбинаций параметров")
    print(f"Период: {from_time.strftime('%Y-%m-%d')} - {to_time.strftime('%Y-%m-%d')} ({days} дней)")
    print(f"Депозит: {deposit:,} руб, используется: {percent_from_deposit}%")
    print("-" * 80)

    combination_count = 0
    processed_count = 0
    
    # Ограничиваем количество комбинаций для ускорения
    if max_combinations and total_combinations > max_combinations:
        print(f"⚠️  Ограничиваем тестирование до {max_combinations} комбинаций из {total_combinations}")
        total_combinations = max_combinations
    
    for params in iter_param_combinations(search_space):
        combination_count += 1
        
        # Пропускаем комбинации если достигли лимита
        if max_combinations and processed_count >= max_combinations:
            break
            
        processed_count += 1
        
        signal_manager = SignalManager(**params)
        # Создаем RiskManager для стратегий
        risk_limits = RiskLimits(
            max_daily_loss=10000,
            max_position_size=100000,
            percent_from_deposit=percent_from_deposit,
            items_per_trade=items_per_trade,
            stop_loss_threshold=8
        )
        
        # Создаем моки для обязательных параметров
        mock_risk_manager = Mock()
        mock_portfolio_manager = Mock()
        
        strategy_manager = StrategyManager(
            signal_manager=signal_manager,
            risk_manager=mock_risk_manager,
            portfolio_manager=mock_portfolio_manager,
            strategies=[
                LongStrategy(risk_manager=mock_risk_manager, portfolio_manager=mock_portfolio_manager),
                ShortStrategy(risk_manager=mock_risk_manager, portfolio_manager=mock_portfolio_manager),
            ],
        )
        result = await run_backtest_from_sqlite(
            db_path=db_path,
            figi=figi,
            from_time=from_time,
            to_time=to_time,
            strategy_manager=strategy_manager,
        )
        income = result["income"]
        
        # Расчет дневной доходности
        daily_income = income / days
        daily_return_pct = (daily_income / (deposit * percent_from_deposit / 100)) * 100
        
        print(f"[{processed_count:3d}/{total_combinations}] Доход: {income:8,.0f} руб | "
              f"За день: {daily_income:6,.0f} руб | "
              f"Доходность: {daily_return_pct:5.2f}%/день | "
              f"MACD({params['macd_fast']},{params['macd_slow']},{params['macd_signal']})")
        
        if income > best["income"]:
            best = {"income": income, "params": params}
            print(f"  ⭐ НОВЫЙ ЛУЧШИЙ РЕЗУЛЬТАТ! Доходность: {daily_return_pct:.2f}%/день")

    print("-" * 80)
    if best["params"]:
        best_daily_income = best["income"] / days
        best_daily_return = (best_daily_income / (deposit * percent_from_deposit / 100)) * 100
        print(f"🏆 ЛУЧШИЙ РЕЗУЛЬТАТ:")
        print(f"   Общий доход: {best['income']:,.0f} руб за {days} дней")
        print(f"   Дневная доходность: {best_daily_return:.2f}%")
        print(f"   Параметры: {best['params']}")

    return best
