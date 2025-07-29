#!/usr/bin/env python3
"""
Визуализатор рыночных данных
Показывает реальные данные с Tinkoff API в удобном интерфейсе
"""

import sys
from pathlib import Path

# Добавляем корневую папку проекта в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from visualization.trading_visualizer import TradingSignalsVisualizer

def main():
    """Главная функция"""
    visualizer = TradingSignalsVisualizer(
        figi="FUTIMOEXF000",
        update_interval=1
    )
    visualizer.run()

if __name__ == "__main__":
    main()
