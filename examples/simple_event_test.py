#!/usr/bin/env python3
"""
Простой тест событий
"""
import sys
import os

# Добавляем путь к модулю
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("🚀 Запуск простого теста событий...")

try:
    from robotlib.trading.di_container import TradingSystemContainer
    from robotlib.trading.trading_config import TradingConfig
    from robotlib.trading.event_bus_interface import EventType, TradingEvent
    print("✅ Модули импортированы")
    
    # Создаем конфигурацию
    config = TradingConfig(figi="FUTIMOEXF000", enable_visualization=True)
    print("✅ Конфигурация создана")
    
    # Создаем DI контейнер
    container = TradingSystemContainer(config)
    print("✅ DI контейнер создан")
    
    # Собираем торговую систему
    trading_system = container.build_trading_system()
    print("✅ Торговая система собрана")
    
    # Проверяем компоненты
    print(f"📊 Визуализация: {'включена' if trading_system['visualizer'] else 'отключена'}")
    print(f"🚌 EventBus: {type(trading_system['event_bus']).__name__}")
    
    # Получаем EventBus
    event_bus = trading_system['event_bus']
    
    # Создаем счетчик событий
    event_count = [0]  # Используем список для изменения в замыкании
    
    def count_events(event):
        event_count[0] += 1
        print(f"📨 Получено событие #{event_count[0]}: {event.event_type.value}")
    
    # Подписываемся на события
    event_bus.subscribe(EventType.CANDLE_RECEIVED, count_events)
    event_bus.subscribe(EventType.SIGNAL_GENERATED, count_events)
    print("✅ Подписались на события")
    
    # Создаем события
    candle_event = TradingEvent(
        EventType.CANDLE_RECEIVED,
        {'price': 100.0, 'figi': 'FUTIMOEXF000'}
    )
    
    signal_event = TradingEvent(
        EventType.SIGNAL_GENERATED,
        {'signal': {'type': 'buy'}, 'figi': 'FUTIMOEXF000'}
    )
    
    # Публикуем события
    import asyncio
    asyncio.run(event_bus.publish(candle_event))
    asyncio.run(event_bus.publish(signal_event))
    print("✅ События опубликованы")
    
    print(f"📊 Всего событий: {event_count[0]}")
    print("🎉 Тест завершен успешно!")
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
