#!/usr/bin/env python3
"""
Простой тест EventBus
"""
import sys
import os

# Добавляем путь к модулю
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("🚀 Запуск простого теста...")

try:
    from robotlib.trading.event_bus_interface import EventBus, EventType, TradingEvent
    print("✅ EventBus импортирован успешно")
    
    # Создаем EventBus
    event_bus = EventBus()
    print("✅ EventBus создан успешно")
    
    # Создаем событие
    event = TradingEvent(EventType.CANDLE_RECEIVED, {"price": 100.0})
    print("✅ Событие создано успешно")
    
    # Публикуем событие
    import asyncio
    asyncio.run(event_bus.publish(event))
    print("✅ Событие опубликовано успешно")
    
    print("🎉 Простой тест завершен успешно!")
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
