#!/usr/bin/env python3
"""
Тест с визуализацией
"""
import sys
import os
import asyncio

# Добавляем путь к модулю
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def test_with_visualization():
    print("🚀 Запуск теста с визуализацией...")

    try:
        from robotlib.trading.di_container import TradingSystemContainer
        from robotlib.trading.trading_config import TradingConfig
        from robotlib.trading.event_bus_interface import EventType, TradingEvent
        print("✅ Модули импортированы успешно")
        
        # Создаем конфигурацию
        from robotlib.trading.tinkoff_api_client import TinkoffAPIClient
        config = TradingConfig(figi="FUTIMOEXF000", enable_visualization=True)
        config.tcs_client = TinkoffAPIClient('test_token', 'test_account_id')
        print("✅ Конфигурация создана успешно")
        
        # Создаем DI контейнер с визуализацией
        container = TradingSystemContainer(config)
        print("✅ DI контейнер создан успешно")
        
        # Собираем торговую систему
        trading_system = await container.build_trading_system()
        print("✅ Торговая система собрана успешно")
        
        # Проверяем компоненты
        print(f"📊 Визуализация: {'включена' if trading_system['visualizer'] else 'отключена'}")
        print(f"🚌 EventBus: {type(trading_system['event_bus']).__name__}")
        
        if trading_system['visualizer']:
            print(f"🎨 Визуализатор: {type(trading_system['visualizer']).__name__}")
            
            # Запускаем визуализатор
            await trading_system['visualizer'].start()
            print("✅ Визуализатор запущен")
            
            # Тестируем публикацию событий
            event_bus = trading_system['event_bus']
            
            # Создаем события
            candle_event = TradingEvent(
                EventType.CANDLE_RECEIVED,
                {"candle": None, "price": 100.0, "figi": "FUTIMOEXF000"}
            )
            
            signal_event = TradingEvent(
                EventType.SIGNAL_GENERATED,
                {"signal": {"type": "buy"}, "figi": "FUTIMOEXF000", "price": 100.0}
            )
            
            # Публикуем события
            print("📤 Публикуем событие свечи...")
            await event_bus.publish(candle_event)
            
            print("📤 Публикуем событие сигнала...")
            await event_bus.publish(signal_event)
            
            # Проверяем подписчиков
            candle_subscribers = event_bus.get_subscribers(EventType.CANDLE_RECEIVED)
            signal_subscribers = event_bus.get_subscribers(EventType.SIGNAL_GENERATED)
            
            print(f"👥 Подписчики на свечи: {len(candle_subscribers)}")
            print(f"👥 Подписчики на сигналы: {len(signal_subscribers)}")
            
            # Останавливаем визуализатор
            await trading_system['visualizer'].stop()
            print("✅ Визуализатор остановлен")
        
        print("🎉 Тест с визуализацией завершен успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_with_visualization())
