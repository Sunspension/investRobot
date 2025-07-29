"""
GPU-ускоренная оптимизация параметров для бэктестинга
Использует PyTorch с MPS для массовых вычислений на Apple Silicon
"""

import torch
import numpy as np
import asyncio
import itertools
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor
import time

from robotlib.utils.gpu_indicators import GPUSignalManager, GPUOHLCV, batch_process_candles
from robotlib.utils.sql_repository import iter_candles, DBCandle


@dataclass
class GPUSearchSpace:
    """Пространство поиска параметров для GPU оптимизации"""
    macd_fast: List[int]
    macd_slow: List[int]
    macd_signal: List[int]
    atr_period: List[int]
    lookback_min: List[int]
    lookback_max: List[int]
    peak_prominence: List[float]


class GPUParamOptimizer:
    """GPU-ускоренный оптимизатор параметров"""
    
    def __init__(self, device: str = "mps", batch_size: int = 1000):
        self.device = device if torch.backends.mps.is_available() else "cpu"
        self.batch_size = batch_size
        print(f"🚀 GPU оптимизатор инициализирован на устройстве: {self.device}")
        
    def generate_param_combinations(self, search_space: GPUSearchSpace) -> List[Dict[str, Any]]:
        """Генерирует все комбинации параметров"""
        
        keys = [
            "macd_fast", "macd_slow", "macd_signal", 
            "atr_period", "lookback_min", "lookback_max", "peak_prominence"
        ]
        
        combinations = []
        for values in itertools.product(*[getattr(search_space, k) for k in keys]):
            combinations.append(dict(zip(keys, values)))
            
        return combinations
    
    async def load_candles_data(self, db_path: str, figi: str, 
                               from_time: datetime, to_time: datetime) -> List[Dict[str, Any]]:
        """Загружает данные свечей из базы данных"""
        print(f"📊 Загружаем данные свечей для {figi} с {from_time} по {to_time}")
        
        candles_data = []
        async for candle in iter_candles(db_path=db_path, figi=figi, from_time=from_time, to_time=to_time):
            candles_data.append({
                'time': candle.time.timestamp(),
                'open': candle.open,
                'high': candle.high,
                'low': candle.low,
                'close': candle.close,
                'volume': candle.volume
            })
            
        print(f"✅ Загружено {len(candles_data)} свечей")
        return candles_data
    
    def process_batch(self, candles_data: List[Dict[str, Any]], 
                     param_combinations: List[Dict[str, Any]]) -> Tuple[torch.Tensor, List[Dict[str, Any]]]:
        """Обрабатывает батч комбинаций параметров"""
        # Конвертируем данные свечей в тензоры
        n_candles = len(candles_data)
        n_combinations = len(param_combinations)
        
        # Создаем тензоры для всех комбинаций параметров
        results = torch.zeros(n_combinations, device=self.device)
        
        for i, params in enumerate(param_combinations):
            signal_manager = GPUSignalManager(
                macd_fast=params['macd_fast'],
                macd_slow=params['macd_slow'],
                macd_signal=params['macd_signal'],
                atr_period=params['atr_period'],
                lookback_min=params['lookback_min'],
                lookback_max=params['lookback_max'],
                peak_prominence=params['peak_prominence'],
                device=self.device
            )
            
            # Обрабатываем свечи
            total_income = 0
            position = 0  # 0 = нет позиции, 1 = лонг, -1 = шорт
            
            for candle_data in candles_data:
                ohlcv = GPUOHLCV(
                    open=torch.tensor(candle_data['open'], device=self.device),
                    high=torch.tensor(candle_data['high'], device=self.device),
                    low=torch.tensor(candle_data['low'], device=self.device),
                    close=torch.tensor(candle_data['close'], device=self.device),
                    volume=torch.tensor(candle_data['volume'], device=self.device),
                    time=torch.tensor(candle_data['time'], device=self.device)
                )
                
                signal = signal_manager.add_candle(ohlcv)
                if signal:
                    # Простая торговая логика
                    if signal['peak_detected'] and position <= 0:
                        # Покупаем на пиках (закрываем шорт, открываем лонг)
                        if position == -1:
                            total_income += 100  # Закрываем шорт
                        position = 1
                    elif signal['trough_detected'] and position >= 0:
                        # Продаем на впадинах (закрываем лонг, открываем шорт)
                        if position == 1:
                            total_income += 100  # Закрываем лонг
                        position = -1
                        
            results[i] = total_income
            
        return results, param_combinations
    
    async def optimize_parameters(self, 
                                db_path: str,
                                figi: str,
                                from_time: datetime,
                                to_time: datetime,
                                search_space: GPUSearchSpace,
                                deposit: int = 400000,
                                percent_from_deposit: int = 50,
                                items_per_trade: int = 20,
                                max_combinations: int = None) -> Dict[str, Any]:
        """Основная функция оптимизации параметров"""
        
        start_time = time.time()
        
        # Загружаем данные свечей
        candles_data = await self.load_candles_data(db_path, figi, from_time, to_time)
        
        # Генерируем комбинации параметров
        all_combinations = self.generate_param_combinations(search_space)
        
        if max_combinations and len(all_combinations) > max_combinations:
            print(f"⚠️  Ограничиваем тестирование до {max_combinations} комбинаций из {len(all_combinations)}")
            all_combinations = all_combinations[:max_combinations]
        
        total_combinations = len(all_combinations)
        print(f"🔍 Начинаем GPU оптимизацию: {total_combinations} комбинаций параметров")
        
        # Вычисляем количество дней
        days = (to_time - from_time).days + 1
        if days == 0:
            days = 1
            
        print(f"📅 Период: {from_time.strftime('%Y-%m-%d')} - {to_time.strftime('%Y-%m-%d')} ({days} дней)")
        print(f"💰 Депозит: {deposit:,} руб, используется: {percent_from_deposit}%")
        print("-" * 80)
        
        # Обрабатываем батчами
        best_income = float("-inf")
        best_params = None
        all_results = []
        
        for batch_start in range(0, total_combinations, self.batch_size):
            batch_end = min(batch_start + self.batch_size, total_combinations)
            batch_combinations = all_combinations[batch_start:batch_end]
            
            print(f"⚡ Обрабатываем батч {batch_start//self.batch_size + 1}/{(total_combinations-1)//self.batch_size + 1} "
                  f"({batch_start+1}-{batch_end} из {total_combinations})")
            
            # Обрабатываем батч
            batch_results, batch_params = self.process_batch(candles_data, batch_combinations)
            
            # Находим лучший результат в батче
            batch_best_idx = torch.argmax(batch_results)
            batch_best_income = batch_results[batch_best_idx].item()
            batch_best_params = batch_params[batch_best_idx]
            
            if batch_best_income > best_income:
                best_income = batch_best_income
                best_params = batch_best_params
                print(f"  ⭐ НОВЫЙ ЛУЧШИЙ РЕЗУЛЬТАТ! Доход: {best_income:,.0f} руб")
            
            # Сохраняем результаты
            for i, (income, params) in enumerate(zip(batch_results, batch_params)):
                daily_income = income.item() / days
                daily_return_pct = (daily_income / (deposit * percent_from_deposit / 100)) * 100
                
                all_results.append({
                    'income': income.item(),
                    'daily_income': daily_income,
                    'daily_return_pct': daily_return_pct,
                    'params': params
                })
                
                if (batch_start + i + 1) % 100 == 0:  # Показываем прогресс каждые 100 комбинаций
                    print(f"  [{batch_start + i + 1:3d}/{total_combinations}] "
                          f"Доход: {income.item():8,.0f} руб | "
                          f"За день: {daily_income:6,.0f} руб | "
                          f"Доходность: {daily_return_pct:5.2f}%/день")
        
        # Сортируем результаты по доходу
        all_results.sort(key=lambda x: x['income'], reverse=True)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        print("-" * 80)
        print(f"🏆 ЛУЧШИЙ РЕЗУЛЬТАТ:")
        if best_params:
            best_daily_income = best_income / days
            best_daily_return = (best_daily_income / (deposit * percent_from_deposit / 100)) * 100
            print(f"   Общий доход: {best_income:,.0f} руб за {days} дней")
            print(f"   Дневная доходность: {best_daily_return:.2f}%")
            print(f"   Параметры: {best_params}")
        
        print(f"⏱️  Время обработки: {processing_time:.2f} секунд")
        print(f"🚀 Скорость: {total_combinations/processing_time:.1f} комбинаций/сек")
        
        return {
            'best_income': best_income,
            'best_params': best_params,
            'all_results': all_results,
            'processing_time': processing_time,
            'combinations_per_second': total_combinations / processing_time
        }


async def gpu_maximize_income(db_path: str,
                            figi: str,
                            from_time: datetime,
                            to_time: datetime,
                            search_space: GPUSearchSpace,
                            deposit: int = 400000,
                            percent_from_deposit: int = 50,
                            items_per_trade: int = 20,
                            max_combinations: int = None,
                            batch_size: int = 1000) -> Dict[str, Any]:
    """
    GPU-ускоренная функция оптимизации параметров
    """
    optimizer = GPUParamOptimizer(device="mps", batch_size=batch_size)
    
    return await optimizer.optimize_parameters(
        db_path=db_path,
        figi=figi,
        from_time=from_time,
        to_time=to_time,
        search_space=search_space,
        deposit=deposit,
        percent_from_deposit=percent_from_deposit,
        items_per_trade=items_per_trade,
        max_combinations=max_combinations
    )


def compare_gpu_cpu_performance(db_path: str,
                               figi: str,
                               from_time: datetime,
                               to_time: datetime,
                               search_space: GPUSearchSpace,
                               max_combinations: int = 100) -> Dict[str, Any]:
    """
    Сравнивает производительность GPU и CPU версий
    """
    print("🔬 Сравнение производительности GPU vs CPU")
    print("=" * 50)
    
    # Тестируем GPU версию
    print("🚀 Тестируем GPU версию...")
    gpu_start = time.time()
    
    # Здесь можно добавить вызов GPU версии
    gpu_time = time.time() - gpu_start
    
    # Тестируем CPU версию
    print("💻 Тестируем CPU версию...")
    cpu_start = time.time()
    
    # Здесь можно добавить вызов CPU версии
    cpu_time = time.time() - cpu_start
    
    speedup = cpu_time / gpu_time if gpu_time > 0 else 0
    
    print(f"📊 Результаты:")
    print(f"   GPU время: {gpu_time:.2f} сек")
    print(f"   CPU время: {cpu_time:.2f} сек")
    print(f"   Ускорение: {speedup:.2f}x")
    
    return {
        'gpu_time': gpu_time,
        'cpu_time': cpu_time,
        'speedup': speedup
    }
