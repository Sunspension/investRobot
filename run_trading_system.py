#!/usr/bin/env python3
"""
Единый entry point для запуска торговой системы
"""
import asyncio
import sys
import os
import argparse
from typing import Optional

# Добавляем путь к модулю
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from robotlib.trading.di_container import TradingSystemContainer
from robotlib.trading.trading_config import TradingConfig
from robotlib.trading.event_bus_interface import EventType, TradingEvent
from robotlib.utils.logger import get_logger


async def run_trading_system(
    figi: str = "FUTIMOEXF000",
    enable_visualization: bool = True,
    host: str = "127.0.0.1",
    port: int = 8050
):
    """Запускает торговую систему с указанными параметрами"""
    
    logger = get_logger(__name__)
    logger.info("🚀 Запуск торговой системы")
    logger.info(f"📊 FIGI: {figi}")
    logger.info(f"📈 Визуализация: {'включена' if enable_visualization else 'отключена'}")
    
    if enable_visualization:
        logger.info(f"🌐 Визуализатор будет доступен по адресу: http://{host}:{port}")
    
    # Загружаем конфигурацию
    from config_data.config import load_config
    config = load_config()
    
    # Создаем торговую конфигурацию
    trading_config = TradingConfig(
        figi=figi,
        enable_visualization=enable_visualization
    )
    
    # Добавляем tcs_client в торговую конфигурацию
    trading_config.tcs_client = config.tcs_client
    
    # Создаем DI контейнер
    container = TradingSystemContainer(trading_config, enable_visualization=enable_visualization)
    trading_system = await container.build_trading_system(host=host, port=port)
    
    logger.info("✅ Торговая система собрана через DI контейнер")
    logger.info(f"🚌 EventBus: {type(trading_system['event_bus']).__name__}")
    
    # Запускаем визуализатор (если включен)
    if trading_system['visualizer']:
        await trading_system['visualizer'].start()
        logger.info("✅ Dash визуализатор событий запущен")
    
    # Получаем EventBus для настройки обработчиков
    event_bus = trading_system['event_bus']
    
    # Создаем обработчики событий
    def handle_portfolio_event(event: TradingEvent):
        total_amount = event.data.get('total_amount', 0)
        positions_count = event.data.get('positions_count', 0)
        logger.info(f"📊 Портфель обновлен: {total_amount:.2f} руб, позиций: {positions_count}")
    
    def handle_signal_event(event: TradingEvent):
        signal = event.data.get('signal')
        if signal:
            # Определяем тип сигнала по MACD
            signal_type = "BUY" if signal.histogram > 0 else "SELL" if signal.histogram < 0 else "NEUTRAL"
            strength = abs(signal.histogram) if signal.histogram else 0
            logger.info(f"📈 Сигнал сгенерирован: {signal_type} (сила: {strength:.4f})")
    
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
    
    # Подписываем SignalManager на события свечей
    signal_manager = trading_system['dependencies'].signal_manager
    signal_manager.subscribe_to_events()
    logger.info("📊 SignalManager подписан на события свечей")
    
    # Получаем SessionController
    session_controller = trading_system['session_controller']
    
    logger.info("🎮 Запуск торговой сессии...")
    try:
        await session_controller.start()
        logger.info("✅ Торговая сессия запущена успешно")
        
        # Ждем до прерывания
        while True:
            await asyncio.sleep(1)
        
    except KeyboardInterrupt:
        logger.info("⏹️ Остановка по запросу пользователя")
    except Exception as e:
        logger.error(f"❌ Ошибка в торговой сессии: {e}")
        raise
    finally:
        logger.info("🛑 Остановка торговой системы...")
        
        # Останавливаем визуализатор
        if trading_system['visualizer']:
            await trading_system['visualizer'].stop()
            logger.info("✅ Визуализатор остановлен")
        
        await session_controller.stop()
        logger.info("✅ Торговая система остановлена")


def main():
    """Основная функция с парсингом аргументов командной строки"""
    parser = argparse.ArgumentParser(description="Запуск торговой системы")
    parser.add_argument(
        "--figi", 
        default="FUTIMOEXF000", 
        help="FIGI инструмента для торговли (по умолчанию: FUTIMOEXF000)"
    )
    parser.add_argument(
        "--no-visualization", 
        action="store_true", 
        help="Отключить визуализацию"
    )
    parser.add_argument(
        "--host", 
        default="127.0.0.1", 
        help="Хост для визуализатора (по умолчанию: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=8050, 
        help="Порт для визуализатора (по умолчанию: 8050)"
    )
    
    args = parser.parse_args()
    
    # Запускаем торговую систему
    asyncio.run(run_trading_system(
        figi=args.figi,
        enable_visualization=not args.no_visualization,
        host=args.host,
        port=args.port
    ))


if __name__ == "__main__":
    main()

