"""
Пример использования торговой системы с новой Event-Driven архитектурой
"""
import asyncio
import sys
import os

# Добавляем путь к модулю
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from robotlib.trading.di_container import TradingSystemContainer
from robotlib.trading.trading_config import TradingConfig
from robotlib.trading.event_bus_interface import EventType, TradingEvent
from robotlib.utils.logger import get_logger


async def main():
    """Пример запуска торговой системы с новой архитектурой"""
    
    logger = get_logger(__name__)
    logger.info("🚀 Запуск торговой системы с Event-Driven архитектурой")
    
    # Создаем конфигурацию
    config = TradingConfig(
        figi="FUTIMOEXF000",
        enable_visualization=False  # Отключаем визуализацию для простого примера
    )
    
    # Создаем DI контейнер
    container = TradingSystemContainer(config)
    trading_system = container.build_trading_system()
    
    logger.info("✅ Торговая система собрана через DI контейнер")
    logger.info(f"🚌 EventBus: {type(trading_system['event_bus']).__name__}")
    
    # Получаем EventBus для демонстрации событий
    event_bus = trading_system['event_bus']
    
    # Создаем обработчики событий для демонстрации
    def handle_portfolio_event(event: TradingEvent):
        logger.info(f"📊 Портфель обновлен: {event.data.get('total_amount', 0):.2f} руб")
    
    def handle_signal_event(event: TradingEvent):
        signal = event.data.get('signal')
        if signal:
            peak_info = "пик" if signal.peak_detected else "впадина" if signal.trough_detected else "нет"
            logger.info(f"📈 Сигнал сгенерирован: MACD={signal.macd:.3f}, {peak_info}")
    
    def handle_order_event(event: TradingEvent):
        order_id = event.data.get('order_id', 'unknown')
        logger.info(f"📋 Ордер {event.event_type.value}: {order_id}")
    
    # Подписываемся на события
    event_bus.subscribe(EventType.PORTFOLIO_UPDATED, handle_portfolio_event)
    event_bus.subscribe(EventType.SIGNAL_GENERATED, handle_signal_event)
    event_bus.subscribe(EventType.ORDER_PLACED, handle_order_event)
    event_bus.subscribe(EventType.ORDER_FILLED, handle_order_event)
    
    logger.info("👥 Подписались на события торговой системы")
    
    # Публикуем тестовые события для демонстрации
    logger.info("📤 Публикуем тестовые события...")
    
    # Событие обновления портфеля
    portfolio_event = TradingEvent(
        EventType.PORTFOLIO_UPDATED,
        {
            'total_amount': 100000.0,
            'available_amount': 95000.0,
            'positions_count': 0
        }
    )
    await event_bus.publish(portfolio_event)
    
    # Событие генерации сигнала
    from robotlib.signal_manager import Signal
    test_signal = Signal(
        macd=0.5,
        signal=0.3,
        histogram=0.2,
        peak_detected=True
    )
    
    signal_event = TradingEvent(
        EventType.SIGNAL_GENERATED,
        {
            'signal': test_signal,
            'figi': 'FUTIMOEXF000'
        }
    )
    await event_bus.publish(signal_event)
    
    # Событие размещения ордера
    order_event = TradingEvent(
        EventType.ORDER_PLACED,
        {
            'order_id': 'test-order-123',
            'figi': 'FUTIMOEXF000',
            'quantity': 10
        }
    )
    await event_bus.publish(order_event)
    
    logger.info("✅ Тестовые события опубликованы")
    
    # Получаем SessionController
    session_controller = trading_system['session_controller']
    
    logger.info("🎮 Запуск торговой сессии...")
    try:
        await session_controller.start()
        logger.info("✅ Торговая сессия запущена успешно")
        
        # Ждем некоторое время для демонстрации
        await asyncio.sleep(5)
        
    except KeyboardInterrupt:
        logger.info("⏹️ Остановка по запросу пользователя")
    except Exception as e:
        logger.error(f"❌ Ошибка в торговой сессии: {e}")
    finally:
        logger.info("🛑 Остановка торговой системы...")
        await session_controller.stop()
        logger.info("✅ Торговая система остановлена")


if __name__ == "__main__":
    asyncio.run(main())