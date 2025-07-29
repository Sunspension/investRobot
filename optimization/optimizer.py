#!/usr/bin/env python3
"""
Универсальный оптимизатор торговых стратегий
Поддерживает оптимизацию для одного дня, массива дат или периода
"""

import asyncio
import json
import time
import torch
import numpy as np
from numba import jit, prange
from datetime import datetime, timedelta
from pathlib import Path
from robotlib.utils.sql_repository import iter_candles
import itertools
from collections import Counter
import sqlite3
import argparse
from typing import List, Union, Optional

# Настройка GPU
device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
print(f"🚀 Device: {device}")

# Константы
DB_PATH = "./data/market.db"
FIGI = "FUTIMOEXF000"
RESULTS_DIR = Path("./data/optimization_results")
LOGS_DIR = Path("./data/logs")
RESULTS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Оптимизированные размеры батчей
BATCH_SIZE = 1000
GPU_BATCH_SIZE = 10000

# Параметры оптимизации
MACD_FAST_RANGE = range(5, 21)
MACD_SLOW_RANGE = range(10, 31)
MACD_SIGNAL_RANGE = range(5, 16)
ATR_PERIOD_RANGE = range(8, 16)
LOOKBACK_MIN_RANGE = range(3, 21)
LOOKBACK_MAX_RANGE = range(10, 31)
PEAK_PROMINENCE_RANGE = [0.1, 0.15, 0.2, 0.25, 0.3]

@jit(nopython=True, parallel=True)
def calculate_macd_fast(prices, fast, slow, signal):
    """Быстрый расчет MACD с Numba"""
    n = len(prices)
    if n < slow:
        return np.zeros(n), np.zeros(n), np.zeros(n)
    
    ema_fast = np.zeros(n)
    ema_slow = np.zeros(n)
    macd = np.zeros(n)
    signal_line = np.zeros(n)
    
    # Инициализация
    ema_fast[0] = prices[0]
    ema_slow[0] = prices[0]
    
    # Расчет EMA
    alpha_fast = 2.0 / (fast + 1)
    alpha_slow = 2.0 / (slow + 1)
    
    for i in range(1, n):
        ema_fast[i] = alpha_fast * prices[i] + (1 - alpha_fast) * ema_fast[i-1]
        ema_slow[i] = alpha_slow * prices[i] + (1 - alpha_slow) * ema_slow[i-1]
        macd[i] = ema_fast[i] - ema_slow[i]
    
    # Расчет сигнальной линии
    alpha_signal = 2.0 / (signal + 1)
    signal_line[0] = macd[0]
    
    for i in range(1, n):
        signal_line[i] = alpha_signal * macd[i] + (1 - alpha_signal) * signal_line[i-1]
    
    histogram = macd - signal_line
    
    return macd, signal_line, histogram

@jit(nopython=True, parallel=True)
def calculate_atr_fast(high, low, close, period):
    """Быстрый расчет ATR с Numba"""
    n = len(high)
    if n < period:
        return np.zeros(n)
    
    tr = np.zeros(n)
    atr = np.zeros(n)
    
    # True Range
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i-1]),
            abs(low[i] - close[i-1])
        )
    
    # ATR
    atr[period-1] = np.mean(tr[1:period])
    alpha = 1.0 / period
    
    for i in range(period, n):
        atr[i] = alpha * tr[i] + (1 - alpha) * atr[i-1]
    
    return atr

@jit(nopython=True)
def find_peaks_fast(prices, prominence, min_distance=1):
    """Быстрый поиск пиков с Numba"""
    n = len(prices)
    peaks = []
    
    for i in range(1, n-1):
        if (prices[i] > prices[i-1] and 
            prices[i] > prices[i+1] and
            prices[i] >= prominence):
            peaks.append(i)
    
    return np.array(peaks)

@jit(nopython=True)
def backtest_strategy_fast(prices, macd, signal, histogram, atr, 
                          lookback_min, lookback_max, peak_prominence):
    """Быстрый бэктест стратегии с Numba"""
    n = len(prices)
    if n < lookback_max:
        return 0.0, 0, 0
    
    balance = 100000.0
    position = 0
    trades = 0
    wins = 0
    
    for i in range(lookback_max, n):
        # Поиск пиков в окне
        window_start = max(0, i - lookback_max)
        window_end = i - lookback_min
        window_prices = prices[window_start:window_end]
        
        if len(window_prices) < lookback_min:
            continue
            
        peaks = find_peaks_fast(window_prices, peak_prominence)
        
        if len(peaks) == 0:
            continue
        
        # Сигналы MACD
        macd_signal = macd[i] > signal[i] and histogram[i] > histogram[i-1]
        macd_exit = macd[i] < signal[i] or histogram[i] < histogram[i-1]
        
        # Торговля
        if macd_signal and position == 0:
            position = 1
            trades += 1
        elif macd_exit and position == 1:
            position = 0
            if balance > 100000:
                wins += 1
    
    return balance, trades, wins

def get_available_days() -> List[str]:
    """Получает список всех доступных дней из базы данных"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT DISTINCT DATE(time) as date 
        FROM candles 
        WHERE figi = ? 
        ORDER BY date
    """, (FIGI,))
    
    days = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    return days

def get_days_in_range(start_date: str, end_date: str) -> List[str]:
    """Получает все дни в указанном диапазоне"""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    days = []
    current = start
    while current <= end:
        days.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    
    # Фильтруем только существующие дни
    available_days = get_available_days()
    return [day for day in days if day in available_days]

async def load_candles_for_days(days: List[str]) -> dict:
    """Загружает свечи для указанных дней"""
    all_candles = []
    
    for day in days:
        print(f"📊 Загружаем данные за {day}...")
        day_candles = []
        
        async for candle in iter_candles(FIGI, day, day):
            day_candles.append({
                'time': candle.time,
                'open': float(candle.open),
                'high': float(candle.high),
                'low': float(candle.low),
                'close': float(candle.close),
                'volume': int(candle.volume)
            })
        
        all_candles.extend(day_candles)
        print(f"   Загружено {len(day_candles)} свечей")
    
    return {
        'candles': all_candles,
        'days': days,
        'total_candles': len(all_candles)
    }

async def optimize_days(days: List[str], max_combinations: int = 100000) -> dict:
    """Оптимизирует стратегию для указанных дней"""
    print(f"🚀 Начинаем оптимизацию для {len(days)} дней: {', '.join(days)}")
    
    # Загружаем данные
    data = await load_candles_for_days(days)
    candles = data['candles']
    
    if not candles:
        raise ValueError("Нет данных для оптимизации")
    
    print(f"📊 Всего свечей: {len(candles)}")
    
    # Подготавливаем данные
    prices = np.array([c['close'] for c in candles])
    high = np.array([c['high'] for c in candles])
    low = np.array([c['low'] for c in candles])
    close = np.array([c['close'] for c in candles])
    
    # Генерируем комбинации параметров
    combinations = list(itertools.product(
        MACD_FAST_RANGE, MACD_SLOW_RANGE, MACD_SIGNAL_RANGE,
        ATR_PERIOD_RANGE, LOOKBACK_MIN_RANGE, LOOKBACK_MAX_RANGE,
        PEAK_PROMINENCE_RANGE
    ))
    
    # Фильтруем валидные комбинации
    valid_combinations = []
    for combo in combinations:
        macd_fast, macd_slow, macd_signal, atr_period, lookback_min, lookback_max, peak_prominence = combo
        if macd_fast < macd_slow and lookback_min < lookback_max:
            valid_combinations.append(combo)
    
    if len(valid_combinations) > max_combinations:
        valid_combinations = valid_combinations[:max_combinations]
    
    print(f"🔍 Тестируем {len(valid_combinations)} комбинаций...")
    
    # Оптимизация
    best_result = None
    best_balance = 0
    results = []
    
    start_time = time.time()
    
    for i, combo in enumerate(valid_combinations):
        macd_fast, macd_slow, macd_signal, atr_period, lookback_min, lookback_max, peak_prominence = combo
        
        try:
            # Расчет индикаторов
            macd, signal, histogram = calculate_macd_fast(prices, macd_fast, macd_slow, macd_signal)
            atr = calculate_atr_fast(high, low, close, atr_period)
            
            # Бэктест
            balance, trades, wins = backtest_strategy_fast(
                prices, macd, signal, histogram, atr,
                lookback_min, lookback_max, peak_prominence
            )
            
            if balance > best_balance:
                best_balance = balance
                best_result = {
                    'macd_fast': macd_fast,
                    'macd_slow': macd_slow,
                    'macd_signal': macd_signal,
                    'atr_period': atr_period,
                    'lookback_min': lookback_min,
                    'lookback_max': lookback_max,
                    'peak_prominence': peak_prominence,
                    'balance': balance,
                    'trades': trades,
                    'wins': wins,
                    'win_rate': wins / trades if trades > 0 else 0
                }
            
            results.append({
                'params': combo,
                'balance': balance,
                'trades': trades,
                'wins': wins
            })
            
            if i % 1000 == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed
                print(f"   Прогресс: {i+1}/{len(valid_combinations)} ({rate:.0f} комб/сек)")
                
        except Exception as e:
            print(f"   Ошибка в комбинации {combo}: {e}")
            continue
    
    elapsed = time.time() - start_time
    print(f"⏱️ Оптимизация завершена за {elapsed:.1f} секунд")
    print(f"📊 Скорость: {len(valid_combinations)/elapsed:.0f} комб/сек")
    
    # Сохраняем результаты
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = RESULTS_DIR / f"optimization_{timestamp}.json"
    
    output = {
        'days': days,
        'total_candles': len(candles),
        'combinations_tested': len(valid_combinations),
        'optimization_time': elapsed,
        'best_result': best_result,
        'all_results': results[:1000]  # Топ-1000 результатов
    }
    
    with open(results_file, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"💾 Результаты сохранены в {results_file}")
    
    return output

def main():
    """Главная функция с поддержкой аргументов командной строки"""
    parser = argparse.ArgumentParser(description='Универсальный оптимизатор торговых стратегий')
    parser.add_argument('--days', nargs='+', help='Список дней для оптимизации (YYYY-MM-DD)')
    parser.add_argument('--start', help='Начальная дата периода (YYYY-MM-DD)')
    parser.add_argument('--end', help='Конечная дата периода (YYYY-MM-DD)')
    parser.add_argument('--all', action='store_true', help='Оптимизировать все доступные дни')
    parser.add_argument('--max-combinations', type=int, default=100000, help='Максимальное количество комбинаций')
    
    args = parser.parse_args()
    
    # Определяем дни для оптимизации
    if args.all:
        days = get_available_days()
        print(f"📅 Найдено {len(days)} доступных дней")
    elif args.start and args.end:
        days = get_days_in_range(args.start, args.end)
        print(f"📅 Период {args.start} - {args.end}: {len(days)} дней")
    elif args.days:
        days = args.days
        print(f"📅 Указанные дни: {len(days)} дней")
    else:
        # По умолчанию - последние 5 дней
        available_days = get_available_days()
        days = available_days[-5:] if len(available_days) >= 5 else available_days
        print(f"📅 По умолчанию - последние {len(days)} дней")
    
    if not days:
        print("❌ Нет доступных дней для оптимизации")
        return
    
    # Запускаем оптимизацию
    asyncio.run(optimize_days(days, args.max_combinations))

if __name__ == "__main__":
    main()
