#!/usr/bin/env python3
"""
Простой тест DI контейнера
"""
import sys
import os

# Добавляем путь к модулю
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("🚀 Запуск теста DI контейнера...")

try:
    from robotlib.trading.di_container import TradingSystemContainer
    from robotlib.trading.trading_config import TradingConfig
    print("✅ Модули импортированы успешно")
    
    # Создаем конфигурацию
    config = TradingConfig(figi="FUTIMOEXF000", enable_visualization=False)
    print("✅ Конфигурация создана успешно")
    
    # Создаем DI контейнер
    container = TradingSystemContainer(config, enable_visualization=False)
    print("✅ DI контейнер создан успешно")
    
    # Собираем торговую систему
    trading_system = container.build_trading_system()
    print("✅ Торговая система собрана успешно")
    
    # Проверяем компоненты
    print(f"📊 Визуализация: {'включена' if trading_system['visualizer'] else 'отключена'}")
    print(f"🚌 EventBus: {type(trading_system['event_bus']).__name__}")
    print(f"🎮 SessionController: {type(trading_system['session_controller']).__name__}")
    
    # Тестируем EventBus
    event_bus = trading_system['event_bus']
    from robotlib.trading.event_bus_interface import EventType, TradingEvent
    
    # Создаем событие
    event = TradingEvent(EventType.CANDLE_RECEIVED, {"price": 100.0})
    
    # Публикуем событие
    import asyncio
    asyncio.run(event_bus.publish(event))
    print("✅ Событие опубликовано через DI контейнер")
    
    print("🎉 Тест DI контейнера завершен успешно!")
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
