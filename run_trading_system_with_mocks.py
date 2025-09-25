#!/usr/bin/env python3
"""
Запуск торговой системы с мок-данными для демонстрации
"""
import asyncio
import argparse
from robotlib.utils.logger import get_logger
from robotlib.trading.trading_config import TradingConfig
from robotlib.trading.di_container import TradingSystemContainer
from tests.mocks.tinkoff_api_client_mock import MockTinkoffAPIClient
from robotlib.trading.interfaces import TradingDependencies
from robotlib.trading.portfolio_manager import PortfolioManager
from robotlib.trading.order_executor import OrderExecutor
from robotlib.trading.market_data_stream import MarketDataStream
from robotlib.trading_interfaces import MarketStatusSinkable
from tests.mocks.visualizer_mock import MockEventVisualizer


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
        'account_id': 'mock_account',
        'sandbox_token': 'mock_sandbox_token'
    })()
    
    # Добавляем мок-клиент в конфигурацию
    config.tcs_client = mock_tcs_client
    
    # Создаем мок API клиент
    mock_api_client = MockTinkoffAPIClient()
    
    # Создаем DI контейнер
    container = TradingSystemContainer(config)
    
    # Переопределяем API клиенты на моки ПЕРЕД созданием компонентов
    # Монkey patching для DI контейнера
    original_get_portfolio_manager = container.get_portfolio_manager
    original_get_order_executor = container.get_order_executor
    original_get_market_data_stream = container.get_market_data_stream
    original_get_trading_dependencies = container.get_trading_dependencies
    
    async def get_portfolio_manager_with_mock():
        if 'portfolio_manager' not in container._instances:
            container._instances['portfolio_manager'] = PortfolioManager(
                api_client=mock_api_client
            )
        return container._instances['portfolio_manager']
    
    async def get_order_executor_with_mock():
        if 'order_executor' not in container._instances:
            container._instances['order_executor'] = OrderExecutor(
                api_client=mock_api_client,
                order_sink=None
            )
        return container._instances['order_executor']
    
    async def get_market_data_stream_with_mock():
        if 'market_data_stream' not in container._instances:
            container._instances['market_data_stream'] = MarketDataStream(
                api_client=mock_api_client,
                figi=config.figi,
                cache_size=1000
            )
        return container._instances['market_data_stream']
    
    async def get_event_sink_with_mock():
        if 'event_sink' not in container._instances:
            container._instances['event_sink'] = MarketStatusSinkable()
        return container._instances['event_sink']
    
    async def get_trading_dependencies_with_mock():
        if 'trading_dependencies' not in container._instances:
            container._instances['trading_dependencies'] = TradingDependencies(
                api_client=mock_api_client,
                order_executor=await get_order_executor_with_mock(),
                portfolio_manager=await get_portfolio_manager_with_mock(),
                risk_manager=await container.get_risk_manager(),
                signal_manager=container.get_signal_manager(),
                strategy_manager=await container.get_strategy_manager(),
                market_data_stream=await get_market_data_stream_with_mock(),
                event_sink=await get_event_sink_with_mock(),
                session_stats=container.get_session_stats()
            )
        return container._instances['trading_dependencies']
    
    def get_visualizer_with_mock(host="127.0.0.1", port=8050, start_server=True):
        if 'visualizer' not in container._instances:
            container._instances['visualizer'] = MockEventVisualizer(
                host=host,
                port=port,
                start_server=start_server
            )
        return container._instances['visualizer']
    
    # Заменяем методы в контейнере
    container.get_portfolio_manager = get_portfolio_manager_with_mock
    container.get_order_executor = get_order_executor_with_mock
    container.get_market_data_stream = get_market_data_stream_with_mock
    container.get_trading_dependencies = get_trading_dependencies_with_mock
    container.get_visualizer = get_visualizer_with_mock
    
    # Собираем торговую систему
    trading_system = await container.build_trading_system(host=host, port=port, start_server=True)
    
    logger.info("✅ Торговая система собрана с мок-данными")
    
    # Визуализатор будет запущен автоматически в SessionController
    logger.info("✅ Dash визуализатор будет запущен в SessionController")
    
    
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
