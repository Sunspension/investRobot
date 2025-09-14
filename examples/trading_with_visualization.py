"""
Пример использования торговой системы с визуализацией (новая Event-Driven архитектура)
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
    """Пример запуска торговой системы с визуализацией"""
    
    logger = get_logger(__name__)
    logger.info("🚀 Запуск торговой системы с визуализацией (Event-Driven архитектура)")
    
    # Создаем конфигурацию
    config = TradingConfig(
        figi="FUTIMOEXF000",
        enable_visualization=True  # Включаем визуализацию
    )
    
    # Создаем DI контейнер с визуализацией
    container = TradingSystemContainer(config)
    trading_system = container.build_trading_system()
    
    logger.info("✅ Торговая система собрана через DI контейнер")
    logger.info(f"📊 Визуализация: {'включена' if trading_system['visualizer'] else 'отключена'}")
    logger.info(f"🚌 EventBus: {type(trading_system['event_bus']).__name__}")
    
    # Запускаем визуализатор (если есть)
    if trading_system['visualizer']:
        await trading_system['visualizer'].start()
        logger.info("✅ Dash визуализатор событий запущен")
        logger.info("🌐 Визуализатор доступен по адресу: http://127.0.0.1:8050")
    else:
        logger.info("⚠️ Визуализатор недоступен")
    
    # Получаем EventBus для демонстрации событий
    event_bus = trading_system['event_bus']
    
    # Создаем обработчики событий для демонстрации
    def handle_portfolio_event(event: TradingEvent):
        total_amount = event.data.get('total_amount', 0)
        positions_count = event.data.get('positions_count', 0)
        logger.info(f"📊 Портфель обновлен: {total_amount:.2f} руб, позиций: {positions_count}")
    
    def handle_signal_event(event: TradingEvent):
        signal = event.data.get('signal')
        if signal:
            peak_info = "пик" if signal.peak_detected else "впадина" if signal.trough_detected else "нет"
            logger.info(f"📈 Сигнал сгенерирован: MACD={signal.macd:.3f}, {peak_info}")
    
    def handle_order_event(event: TradingEvent):
        order_id = event.data.get('order_id', 'unknown')
        event_type = event.event_type.value
        logger.info(f"📋 Ордер {event_type}: {order_id}")
    
    def handle_candle_event(event: TradingEvent):
        price = event.data.get('price', 0)
        figi = event.data.get('figi', 'unknown')
        logger.info(f"🕯️ Получена свеча: {figi} @ {price}")
    
    # Подписываемся на события
    event_bus.subscribe(EventType.PORTFOLIO_UPDATED, handle_portfolio_event)
    event_bus.subscribe(EventType.SIGNAL_GENERATED, handle_signal_event)
    event_bus.subscribe(EventType.ORDER_PLACED, handle_order_event)
    event_bus.subscribe(EventType.ORDER_FILLED, handle_order_event)
    event_bus.subscribe(EventType.CANDLE_RECEIVED, handle_candle_event)
    
    logger.info("👥 Подписались на события торговой системы")
    
    # Публикуем тестовые события для демонстрации
    logger.info("📤 Публикуем тестовые события...")
    
    # Событие получения свечи
    candle_event = TradingEvent(
        EventType.CANDLE_RECEIVED,
        {
            'candle': None,  # Мок свеча
            'price': 100.0,
            'figi': 'FUTIMOEXF000'
        }
    )
    await event_bus.publish(candle_event)
    
    # Событие обновления портфеля
    portfolio_event = TradingEvent(
        EventType.PORTFOLIO_UPDATED,
        {
            'total_amount': 100000.0,
            'available_amount': 95000.0,
            'positions_count': 0,
            'variation_margin': 0.0,
            'guarantee_deposit': 0.0,
            'pnl': 0.0
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
            'candle': None,
            'figi': 'FUTIMOEXF000',
            'timestamp': None
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
        await asyncio.sleep(10)
        
    except KeyboardInterrupt:
        logger.info("⏹️ Остановка по запросу пользователя")
    except Exception as e:
        logger.error(f"❌ Ошибка в торговой сессии: {e}")
    finally:
        logger.info("🛑 Остановка торговой системы...")
        
        # Останавливаем визуализатор
        if trading_system['visualizer']:
            await trading_system['visualizer'].stop()
            logger.info("✅ Визуализатор остановлен")
        
        await session_controller.stop()
        logger.info("✅ Торговая система остановлена")


if __name__ == "__main__":
    asyncio.run(main())