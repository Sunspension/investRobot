#!/usr/bin/env python3
"""
Запуск торговой системы с мок-данными для демонстрации
"""
import asyncio
import argparse
from robotlib.utils.logger import get_logger
from robotlib.trading.trading_config import TradingConfig
from robotlib.trading.di_container import TradingSystemContainer
from robotlib.trading.event_bus_interface import EventType, TradingEvent
from tests.mocks.tinkoff_api_client_mock import MockTinkoffAPIClient

logger = get_logger(__name__)

async def run_trading_system_with_mocks(
    figi: str = "FUTIMOEXF000",
    enable_visualization: bool = True,
    host: str = "127.0.0.1",
    port: int = 8050
):
    """Запускает торговую систему с мок-данными"""
    
    # Создаем конфигурацию
    config = TradingConfig(figi=figi)
    
    # Создаем мок-конфигурацию для API клиента
    mock_tcs_client = type('MockTCSClient', (), {
        'token': 'mock_token',
        'id': 'mock_account',
        'sandbox_token': 'mock_sandbox_token'
    })()
    
    # Добавляем мок-клиент в конфигурацию
    config.tcs_client = mock_tcs_client
    
    # Создаем мок API клиент
    mock_api_client = MockTinkoffAPIClient()
    
    # Создаем DI контейнер
    container = TradingSystemContainer(config, enable_visualization=enable_visualization)
    
    # Переопределяем API клиенты на моки ПЕРЕД созданием компонентов
    # Монkey patching для DI контейнера
    original_get_portfolio_manager = container.get_portfolio_manager
    original_get_order_executor = container.get_order_executor
    original_get_market_data_stream = container.get_market_data_stream
    original_get_trading_dependencies = container.get_trading_dependencies
    
    def get_portfolio_manager_with_mock():
        if 'portfolio_manager' not in container._instances:
            from robotlib.trading.portfolio_manager import PortfolioManager
            container._instances['portfolio_manager'] = PortfolioManager(
                api_client=mock_api_client,
                event_bus=container.get_event_bus()
            )
        return container._instances['portfolio_manager']
    
    def get_order_executor_with_mock():
        if 'order_executor' not in container._instances:
            from robotlib.trading.order_executor import OrderExecutor
            container._instances['order_executor'] = OrderExecutor(
                api_client=mock_api_client,
                event_bus=container.get_event_bus()
            )
        return container._instances['order_executor']
    
    def get_market_data_stream_with_mock():
        if 'market_data_stream' not in container._instances:
            from robotlib.trading.market_data_stream import MarketDataStream
            container._instances['market_data_stream'] = MarketDataStream(
                api_client=mock_api_client,
                figi=config.figi,
                signal_manager=container.get_signal_manager(),
                visualizer=None,
                cache_size=1000,
                event_bus=container.get_event_bus()
            )
        return container._instances['market_data_stream']
    
    def get_trading_dependencies_with_mock():
        if 'trading_dependencies' not in container._instances:
            from robotlib.trading.interfaces import TradingDependencies
            container._instances['trading_dependencies'] = TradingDependencies(
                api_client=mock_api_client,
                session_stats=container.get_session_stats(),
                session_initializer=None,
                portfolio_manager=container.get_portfolio_manager(),
                risk_manager=container.get_risk_manager(),
                order_executor=container.get_order_executor(),
                market_data_stream=container.get_market_data_stream(),
                signal_manager=container.get_signal_manager(),
                strategy_manager=container.get_strategy_manager()
            )
        return container._instances['trading_dependencies']
    
    # Заменяем методы в контейнере
    container.get_portfolio_manager = get_portfolio_manager_with_mock
    container.get_order_executor = get_order_executor_with_mock
    container.get_market_data_stream = get_market_data_stream_with_mock
    container.get_trading_dependencies = get_trading_dependencies_with_mock
    
    # Собираем торговую систему
    trading_system = container.build_trading_system(host=host, port=port)
    
    logger.info("✅ Торговая система собрана с мок-данными")
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
    
    # Запускаем торговую систему
    try:
        await trading_system['session_controller'].start()
        logger.info("✅ Торговая система запущена")
        
        # Ждем завершения
        await asyncio.sleep(3600)  # Работаем 1 час
        
    except KeyboardInterrupt:
        logger.info("🛑 Получен сигнал остановки")
    finally:
        # Останавливаем систему
        if trading_system['session_controller']:
            await trading_system['session_controller'].stop()
        
        if trading_system['visualizer']:
            await trading_system['visualizer'].stop()
        
        logger.info("✅ Торговая система остановлена")

def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description="Запуск торговой системы с мок-данными")
    parser.add_argument(
        "--figi", 
        default="FUTIMOEXF000", 
        help="FIGI инструмента (по умолчанию: FUTIMOEXF000)"
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
    asyncio.run(run_trading_system_with_mocks(
        figi=args.figi,
        enable_visualization=not args.no_visualization,
        host=args.host,
        port=args.port
    ))

if __name__ == "__main__":
    main()
