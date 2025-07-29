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
    
    # Создаем торговую сессию
    session = TradingSession(
        config=trading_config,
        token=config.tcs_client.token,
        account_id=config.tcs_client.id,
        sandbox_token=getattr(config.tcs_client, 'sandbox_token', None)
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
