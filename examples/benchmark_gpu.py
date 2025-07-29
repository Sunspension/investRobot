#!/usr/bin/env python3
"""
Бенчмарк производительности GPU vs CPU для оптимизации параметров
"""

import asyncio
import time
import click
from datetime import datetime
from robotlib.utils.gpu_param_search import gpu_maximize_income, GPUSearchSpace
from robotlib.utils.param_search import maximize_income, SearchSpace


@click.command()
@click.option('--db', default='./data/market.db', help='Путь к базе данных SQLite')
@click.option('--figi', default='FUTIMOEXF000', help='FIGI инструмента')
@click.option('--from', 'from_time', default='2024-12-02 07:00', help='Начальная дата')
@click.option('--to', 'to_time', default='2024-12-30 18:59', help='Конечная дата')
@click.option('--max-combinations', default=100, help='Количество комбинаций для теста')
def main(db, figi, from_time, to_time, max_combinations):
    """
    Сравнивает производительность GPU и CPU версий оптимизации
    """
    
    # Парсим даты
    from_dt = datetime.strptime(from_time, '%Y-%m-%d %H:%M')
    to_dt = datetime.strptime(to_time, '%Y-%m-%d %H:%M')
    
    # Определяем пространство поиска параметров
    gpu_search_space = GPUSearchSpace(
        macd_fast=[6, 8, 10],
        macd_slow=[11, 15, 19],
        macd_signal=[7, 9, 11],
        atr_period=[5, 7, 9],
        lookback_min=[6, 8],
        lookback_max=[15, 18],
        peak_prominence=[0.1, 0.15, 0.2]
    )
    
    cpu_search_space = SearchSpace(
        macd_fast=[6, 8, 10],
        macd_slow=[11, 15, 19],
        macd_signal=[7, 9, 11],
        atr_period=[5, 7, 9],
        lookback_min=[6, 8],
        lookback_max=[15, 18],
        peak_prominence=[0.1, 0.15, 0.2]
    )
    
    print("🔬 Бенчмарк производительности GPU vs CPU")
    print("=" * 60)
    print(f"📊 Инструмент: {figi}")
    print(f"📅 Период: {from_dt.strftime('%Y-%m-%d %H:%M')} - {to_dt.strftime('%Y-%m-%d %H:%M')}")
    print(f"🔢 Количество комбинаций: {max_combinations}")
    print("=" * 60)
    
    async def run_benchmark():
        # Тестируем GPU версию
        print("\n🚀 Тестируем GPU версию...")
        gpu_start = time.time()
        
        gpu_result = await gpu_maximize_income(
            db_path=db,
            figi=figi,
            from_time=from_dt,
            to_time=to_dt,
            search_space=gpu_search_space,
            max_combinations=max_combinations,
            batch_size=50  # Меньший батч для теста
        )
        
        gpu_time = time.time() - gpu_start
        
        # Тестируем CPU версию
        print("\n💻 Тестируем CPU версию...")
        cpu_start = time.time()
        
        cpu_result = await maximize_income(
            db_path=db,
            figi=figi,
            from_time=from_dt,
            to_time=to_dt,
            search_space=cpu_search_space,
            max_combinations=max_combinations
        )
        
        cpu_time = time.time() - cpu_start
        
        # Вычисляем ускорение
        speedup = cpu_time / gpu_time if gpu_time > 0 else 0
        
        print("\n" + "=" * 60)
        print("📊 РЕЗУЛЬТАТЫ БЕНЧМАРКА:")
        print("=" * 60)
        print(f"🚀 GPU время: {gpu_time:.2f} секунд")
        print(f"💻 CPU время: {cpu_time:.2f} секунд")
        print(f"⚡ Ускорение: {speedup:.2f}x")
        print(f"📈 GPU скорость: {max_combinations/gpu_time:.1f} комбинаций/сек")
        print(f"📈 CPU скорость: {max_combinations/cpu_time:.1f} комбинаций/сек")
        
        # Сравниваем результаты
        print(f"\n🏆 ЛУЧШИЕ РЕЗУЛЬТАТЫ:")
        print(f"GPU лучший доход: {gpu_result['best_income']:,.0f} руб")
        print(f"CPU лучший доход: {cpu_result['income']:,.0f} руб")
        
        if gpu_result['best_income'] > cpu_result['income']:
            print("✅ GPU версия дала лучший результат!")
        elif cpu_result['income'] > gpu_result['best_income']:
            print("✅ CPU версия дала лучший результат!")
        else:
            print("🤝 Результаты одинаковые!")
        
        # Рекомендации
        print(f"\n💡 РЕКОМЕНДАЦИИ:")
        if speedup > 2:
            print("🚀 GPU версия значительно быстрее - рекомендуется для регулярного использования!")
        elif speedup > 1.5:
            print("⚡ GPU версия быстрее - стоит использовать для больших объемов данных")
        elif speedup > 1.1:
            print("📈 GPU версия немного быстрее - можно использовать")
        else:
            print("💻 CPU версия работает хорошо - GPU ускорение не критично")
        
        return {
            'gpu_time': gpu_time,
            'cpu_time': cpu_time,
            'speedup': speedup,
            'gpu_result': gpu_result,
            'cpu_result': cpu_result
        }
    
    # Запускаем бенчмарк
    result = asyncio.run(run_benchmark())
    
    print(f"\n✅ Бенчмарк завершен!")


if __name__ == '__main__':
    main()
