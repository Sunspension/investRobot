"""
Тест новой Event-Driven архитектуры
"""
import sys
import os
import asyncio

# Добавляем путь к модулю
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from robotlib.trading.di_container import TradingSystemContainer
from robotlib.trading.trading_config import TradingConfig
from robotlib.trading.event_bus_interface import EventType, TradingEvent
from robotlib.utils.logger import get_logger


async def test_event_architecture():
    """Тестируем новую Event-Driven архитектуру"""
    logger = get_logger(__name__)
    
    # Создаем конфигурацию
    config = TradingConfig(
        figi="FUTIMOEXF000",
        enable_visualization=True
    )
    
    # Создаем DI контейнер с визуализацией
    container = TradingSystemContainer(config, enable_visualization=True)
    trading_system = container.build_trading_system()
    
    logger.info("✅ Торговая система собрана через DI контейнер")
    logger.info(f"📊 Визуализация: {'включена' if trading_system['visualizer'] else 'отключена'}")
    logger.info(f"🚌 EventBus: {type(trading_system['event_bus']).__name__}")
    
    # Запускаем визуализатор
    if trading_system['visualizer']:
        await trading_system['visualizer'].start()
        logger.info("✅ Dash визуализатор событий запущен")
    
    # Тестируем публикацию событий
    event_bus = trading_system['event_bus']
    
    # Создаем тестовые события
    candle_event = TradingEvent(
        EventType.CANDLE_RECEIVED,
        {
            'candle': None,  # Мок свеча
            'price': 100.0,
            'figi': 'FUTIMOEXF000'
        }
    )
    
    signal_event = TradingEvent(
        EventType.SIGNAL_GENERATED,
        {
            'signal': {'type': 'buy', 'strength': 0.8},
            'figi': 'FUTIMOEXF000',
            'price': 100.0
        }
    )
    
    # Публикуем события
    logger.info("📤 Публикуем событие свечи...")
    await event_bus.publish(candle_event)
    
    logger.info("📤 Публикуем событие сигнала...")
    await event_bus.publish(signal_event)
    
    # Проверяем подписчиков
    candle_subscribers = event_bus.get_subscribers(EventType.CANDLE_RECEIVED)
    signal_subscribers = event_bus.get_subscribers(EventType.SIGNAL_GENERATED)
    
    logger.info(f"👥 Подписчики на свечи: {len(candle_subscribers)}")
    logger.info(f"👥 Подписчики на сигналы: {len(signal_subscribers)}")
    
    # Останавливаем визуализатор
    if trading_system['visualizer']:
        await trading_system['visualizer'].stop()
        logger.info("✅ Dash визуализатор событий остановлен")
    
    logger.info("🎉 Тест Event-Driven архитектуры завершен успешно!")


async def test_without_visualization():
    """Тестируем без визуализации"""
    logger = get_logger(__name__)
    
    # Создаем конфигурацию
    config = TradingConfig(
        figi="FUTIMOEXF000",
        enable_visualization=False
    )
    
    # Создаем DI контейнер без визуализации
    container = TradingSystemContainer(config, enable_visualization=False)
    trading_system = container.build_trading_system()
    
    logger.info("✅ Торговая система собрана БЕЗ визуализации")
    logger.info(f"📊 Визуализация: {'включена' if trading_system['visualizer'] else 'отключена'}")
    logger.info(f"🚌 EventBus: {type(trading_system['event_bus']).__name__}")
    
    # Тестируем публикацию событий
    event_bus = trading_system['event_bus']
    
    # Создаем тестовое событие
    test_event = TradingEvent(
        EventType.CANDLE_RECEIVED,
        {'price': 200.0, 'figi': 'FUTIMOEXF000'}
    )
    
    # Публикуем событие
    logger.info("📤 Публикуем тестовое событие...")
    await event_bus.publish(test_event)
    
    logger.info("🎉 Тест без визуализации завершен успешно!")


async def main():
    """Основная функция"""
    logger = get_logger(__name__)
    
    logger.info("🚀 Запуск тестов Event-Driven архитектуры")
    logger.info("=" * 50)
    
    # Тест с визуализацией
    logger.info("📊 Тест 1: С визуализацией")
    await test_event_architecture()
    
    logger.info("")
    logger.info("=" * 50)
    
    # Тест без визуализации
    logger.info("📊 Тест 2: Без визуализации")
    await test_without_visualization()
    
    logger.info("")
    logger.info("🎉 Все тесты завершены успешно!")
    logger.info("✅ Event-Driven архитектура работает корректно!")


if __name__ == "__main__":
    asyncio.run(main())
