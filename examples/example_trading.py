"""
Пример использования торговой системы
"""
import asyncio
import logging
from config_data.config import load_config
from robotlib.trading import TradingSession, TradingConfig, RiskLimits


async def main():
    """Пример запуска торговой сессии"""
    
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Загружаем конфигурацию
    config = load_config()
    
    # Настройки риска
    risk_limits = RiskLimits(
        max_daily_loss=1500,      # 1.5k руб
        max_position_size=30000,   # 30k руб
        percent_from_deposit=30,   # 30% от депозита
        items_per_trade=10,        # 10 лотов за сделку
        stop_loss_threshold=5      # 5 пунктов
    )
    
    # Параметры сигнального менеджера (оптимизированные)
    signal_params = {
        'macd_fast': 10,
        'macd_slow': 15,
        'macd_signal': 11,
        'atr_period': 7,
        'lookback_min': 8,
        'lookback_max': 18,
        'peak_prominence': 0.15
    }
    
    # Конфигурация торговли
    trading_config = TradingConfig(
        figi="FUTIMOEXF000",
        deposit=50000,           # 50k руб
        percent_from_deposit=40, # 40% от депозита
        items_per_trade=3,       # 3 лота за сделку
        signal_manager_params=signal_params,
        risk_limits=risk_limits,
        sandbox=True,            # Песочница
        auto_close_positions=True
    )
    
    # Создаем зависимости
    from robotlib.trading.tinkoff_api_client import TinkoffAPIClient
    from robotlib.trading.order_executor import OrderExecutor
    from robotlib.trading.portfolio_manager import PortfolioManager
    from robotlib.trading.risk_manager import RiskManager
    from robotlib.trading.session_stats import SessionStats
    from robotlib.trading.session_initializer import SessionInitializer
    from robotlib.signal_manager import SignalManager
    from robotlib.strategies.strategy_manager import StrategyManager
    from robotlib.utils.market_data_stream import MarketDataStream
    from robotlib.trading.interfaces import TradingDependencies
    
    # Создаем API клиент
    api_client = TinkoffAPIClient(
        token=config.tcs_client.token,
        account_id=config.tcs_client.id,
        sandbox_token=getattr(config.tcs_client, 'sandbox_token', None)
    )
    
    # Создаем компоненты
    order_executor = OrderExecutor(api_client)
    portfolio_manager = PortfolioManager(api_client)
    risk_manager = RiskManager(portfolio_manager, risk_limits)
    signal_manager = SignalManager(**signal_params)
    
    # Создаем поток данных
    market_data_stream = MarketDataStream(
        api_client=api_client,
        signal_manager=signal_manager,
        figi="FUTIMOEXF000"
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
    session_initializer = SessionInitializer(
        api_client=api_client,
        portfolio_manager=portfolio_manager,
        risk_manager=risk_manager,
        signal_manager=signal_manager,
        strategy_manager=strategy_manager,
        market_data_stream=market_data_stream
    )
    
    # Создаем зависимости
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
    
    # Создаем торговую сессию
    session = TradingSession(
        config=trading_config,
        dependencies=dependencies
    )
    
    try:
        print("🚀 Запуск торговой сессии...")
        
        # Запускаем сессию
        if await session.start():
            print("✅ Торговая сессия запущена успешно")
            
            # Получаем статус
            status = await session.get_session_status()
            print(f"📊 Статус: {status}")
            
            # Запускаем основной цикл (будет работать до остановки)
            print("🔄 Запуск основного цикла торговли...")
            await session.run_trading_loop()
            
        else:
            print("❌ Не удалось запустить торговую сессию")
            
    except KeyboardInterrupt:
        print("\n⏹️ Остановка по запросу пользователя")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        print("🛑 Остановка торговой сессии...")
        await session.stop()
        print("✅ Торговая сессия остановлена")


if __name__ == "__main__":
    asyncio.run(main())
