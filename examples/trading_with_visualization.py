#!/usr/bin/env python3
"""
Пример торговли с визуализацией
"""
import asyncio
import sys
import logging
import warnings
from pathlib import Path

# Добавляем корневую папку проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Отключаем избыточные логи Flask/Dash
from visualization.logging_config import disable_verbose_logging
disable_verbose_logging(enable_debug_logs=True)

from robotlib.trading.trading_config import TradingConfig
from robotlib.trading.visualizer_factory import TradingVisualizerFactory
from robotlib.trading.session_controller import SessionController
from robotlib.di.service_locator import ServiceLocator
from robotlib.utils.logger import get_logger, setup_logging


async def main():
    """Главная функция"""
    # Настраиваем логирование
    setup_logging(level=logging.INFO, log_file="data/logs/app.log")
    logger = get_logger(__name__)
    
    try:
        # Создаем конфигурацию с включенной визуализацией
        config = TradingConfig(
            figi="FUTIMOEXF000",
            enable_visualization=True,  # Включаем визуализацию
            auto_close_positions=True,
            end_of_day_close=True
        )
        
        logger.info("Создаем визуализатор...")
        
        # Создаем фабрику визуализатора
        visualizer_factory = TradingVisualizerFactory()
        
        # Создаем визуализатор
        visualizer = visualizer_factory.create_visualizer(
            config=config,
            host="127.0.0.1",
            port=8050
        )
        
        if visualizer:
            logger.info("Визуализатор создан успешно")
        else:
            logger.warning("Визуализатор не создан (отключен в конфигурации)")
        
        # Создаем сервис-локатор
        service_locator = ServiceLocator()
        
        # Инициализация всех зависимостей
        logger.info("Инициализация зависимостей...")
        
        # Импортируем необходимые модули
        from robotlib.trading.tinkoff_api_client import TinkoffAPIClient
        from robotlib.trading.order_executor import OrderExecutor
        from robotlib.trading.portfolio_manager import PortfolioManager
        from robotlib.trading.risk_manager import RiskManager
        from robotlib.trading.session_stats import SessionStats
        from robotlib.trading.session_initializer import SessionInitializer
        from robotlib.signal_manager import SignalManager
        from robotlib.strategies.strategy_manager import StrategyManager
        from robotlib.trading.market_data_stream import MarketDataStream
        from robotlib.trading.interfaces import TradingDependencies
        from robotlib.trading.risk_manager import RiskLimits
        from config_data.config import load_config
        
        # Загружаем конфигурацию
        app_config = load_config()
        
        # Настройки риска
        risk_limits = RiskLimits(
            max_daily_loss=1500,
            max_position_size=30000,
            percent_from_deposit=30,
            items_per_trade=10,
            stop_loss_threshold=5
        )
        
        # Параметры сигнального менеджера
        signal_params = {
            'macd_fast': 10,
            'macd_slow': 15,
            'macd_signal': 11,
            'atr_period': 7,
            'lookback_min': 8,
            'lookback_max': 18,
            'peak_prominence': 0.15
        }
        
        # Создаем API клиент и инициализируем его
        api_client = TinkoffAPIClient(
            token=app_config.tcs_client.token,
            account_id=app_config.tcs_client.id,
            sandbox_token=getattr(app_config.tcs_client, 'sandbox_token', None)
        )
        
        # Инициализируем API клиент
        await api_client.__aenter__()
        
        # Создаем компоненты
        order_executor = OrderExecutor(api_client)
        portfolio_manager = PortfolioManager(api_client)
        risk_manager = RiskManager(portfolio_manager, risk_limits)
        signal_manager = SignalManager(**signal_params)
        
        # Создаем поток данных
        market_data_stream = MarketDataStream(
            api_client=api_client,
            signal_manager=signal_manager,
            figi=config.figi,
            visualizer=visualizer
        )
        
        # Создаем менеджер стратегий
        strategy_manager = StrategyManager(
            signal_manager=signal_manager,
            risk_manager=risk_manager,
            portfolio_manager=portfolio_manager,
            order_executor=order_executor
        )
        
        # Создаем компоненты сессии
        session_stats = SessionStats()
        
        # Создаем зависимости (сначала без session_initializer)
        dependencies = TradingDependencies(
            api_client=api_client,
            order_executor=order_executor,
            portfolio_manager=portfolio_manager,
            risk_manager=risk_manager,
            signal_manager=signal_manager,
            strategy_manager=strategy_manager,
            market_data_stream=market_data_stream,
            session_stats=session_stats,
            session_initializer=None  # Временно None
        )
        
        # Создаем SessionInitializer с правильными параметрами
        session_initializer = SessionInitializer(config, dependencies)
        
        # Обновляем зависимости с правильным SessionInitializer
        dependencies = TradingDependencies(
            api_client=api_client,
            order_executor=order_executor,
            portfolio_manager=portfolio_manager,
            risk_manager=risk_manager,
            signal_manager=signal_manager,
            strategy_manager=strategy_manager,
            market_data_stream=market_data_stream,
            session_stats=session_stats,
            session_initializer=session_initializer
        )
        
        # Создаем контроллер сессии с визуализатором
        session_controller = SessionController(
            config=config,
            dependencies=dependencies,
            force_start=False,  # Проверяем реальное состояние рынка
            visualizer=visualizer
        )
        
        # Обновляем провайдер данных в визуализаторе на реальный
        if visualizer:
            visualizer.update_strategy_data_provider(session_controller)
            logger.info("✅ Провайдер данных визуализатора обновлен на реальный")
        
        logger.info("Торговая система с визуализацией готова к запуску")
        logger.info("Визуализатор будет доступен по адресу: http://127.0.0.1:8050")
        
        # Запускаем сессию
        success = await session_controller.start()
        if success:
            logger.info("Торговая сессия запущена успешно")
            
            # Основной цикл торговли - работаем до получения сигнала остановки
            try:
                while True:
                    await asyncio.sleep(1)  # Проверяем каждую секунду
            except KeyboardInterrupt:
                logger.info("Получен сигнал остановки")
            finally:
                # Останавливаем сессию
                await session_controller.stop()
                logger.info("Торговая сессия остановлена")
        else:
            logger.error("Не удалось запустить торговую сессию")
    
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        raise
    finally:
        # Закрываем API клиент
        if 'api_client' in locals():
            await api_client.__aexit__(None, None, None)
            logger.info("API клиент закрыт")


if __name__ == "__main__":
    asyncio.run(main())
