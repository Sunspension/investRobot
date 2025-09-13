#!/usr/bin/env python3
"""
Тест живых событий в работающей системе
"""
import sys
import os
import asyncio
import time

# Добавляем путь к модулю
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from robotlib.trading.di_container import TradingSystemContainer
from robotlib.trading.trading_config import TradingConfig
from robotlib.trading.event_bus_interface import EventType, TradingEvent
from robotlib.utils.logger import get_logger


async def test_live_events():
    """Тестируем живые события"""
    logger = get_logger(__name__)
    
    logger.info("🚀 Запуск теста живых событий...")
    
    # Создаем конфигурацию
    config = TradingConfig(figi="FUTIMOEXF000", enable_visualization=True)
    
    # Создаем DI контейнер с визуализацией
    container = TradingSystemContainer(config, enable_visualization=True)
    trading_system = container.build_trading_system()
    
    logger.info("✅ Торговая система собрана")
    
    # Запускаем визуализатор
    if trading_system['visualizer']:
        await trading_system['visualizer'].start()
        logger.info("✅ Визуализатор запущен")
    
    # Получаем EventBus
    event_bus = trading_system['event_bus']
    
    # Создаем счетчик событий
    event_count = 0
    
    async def count_events(event):
        nonlocal event_count
        event_count += 1
        logger.info(f"📨 Получено событие #{event_count}: {event.event_type.value}")
    
    # Подписываемся на все события
    event_bus.subscribe(EventType.CANDLE_RECEIVED, count_events)
    event_bus.subscribe(EventType.SIGNAL_GENERATED, count_events)
    event_bus.subscribe(EventType.ORDER_PLACED, count_events)
    event_bus.subscribe(EventType.POSITION_OPENED, count_events)
    event_bus.subscribe(EventType.PORTFOLIO_UPDATED, count_events)
    
    logger.info("👥 Подписались на события")
    
    # Публикуем тестовые события
    for i in range(5):
        # Событие свечи
        candle_event = TradingEvent(
            EventType.CANDLE_RECEIVED,
            {
                'candle': None,
                'price': 100.0 + i,
                'figi': 'FUTIMOEXF000'
            }
        )
        
        # Событие сигнала
        signal_event = TradingEvent(
            EventType.SIGNAL_GENERATED,
            {
                'signal': {'type': 'buy', 'strength': 0.8},
                'figi': 'FUTIMOEXF000',
                'price': 100.0 + i
            }
        )
        
        # Публикуем события
        await event_bus.publish(candle_event)
        await event_bus.publish(signal_event)
        
        logger.info(f"📤 Опубликованы события #{i+1}")
        await asyncio.sleep(0.1)  # Небольшая задержка
    
    # Ждем обработки событий
    await asyncio.sleep(1)
    
    logger.info(f"📊 Всего обработано событий: {event_count}")
    
    # Останавливаем визуализатор
    if trading_system['visualizer']:
        await trading_system['visualizer'].stop()
        logger.info("✅ Визуализатор остановлен")
    
    logger.info("🎉 Тест живых событий завершен!")


if __name__ == "__main__":
    asyncio.run(test_live_events())
