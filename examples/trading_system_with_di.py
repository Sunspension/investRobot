"""
Пример использования торговой системы с DI контейнером
"""
import sys
import os
import asyncio

# Добавляем путь к модулю
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from robotlib.trading.di_container import TradingSystemContainer
from robotlib.trading.trading_config import TradingConfig
from robotlib.utils.logger import get_logger


async def main():
    """Основная функция"""
    logger = get_logger(__name__)
    
    # Создаем конфигурацию
    config = TradingConfig(
        figi="FUTIMOEXF000",
        enable_visualization=True  # Включаем визуализацию
    )
    
    # Создаем DI контейнер
    container = TradingSystemContainer(config, enable_visualization=False)  # Отключаем визуализацию для теста
    
    # Собираем торговую систему
    trading_system = container.build_trading_system()
    
    logger.info("Торговая система собрана через DI контейнер")
    logger.info(f"Визуализация: {'включена' if trading_system['visualizer'] else 'отключена'}")
    
    # Запускаем визуализатор (если есть)
    if trading_system['visualizer']:
        await trading_system['visualizer'].start()
        logger.info("Dash визуализатор событий запущен")
        
        # Получаем адаптер для совместимости
        adapter = trading_system['visualizer'].get_adapter()
        logger.info(f"Адаптер визуализатора: {adapter}")
    else:
        logger.info("Визуализация отключена")
    
    # Запускаем торговую систему
    session_controller = trading_system['session_controller']
    await session_controller.start()
    
    try:
        # Торговая система работает
        logger.info("Торговая система запущена")
        
        # Здесь можно добавить логику торговли
        await asyncio.sleep(10)  # Пример работы
        
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")
    finally:
        # Останавливаем визуализатор
        if trading_system['visualizer']:
            await trading_system['visualizer'].stop()
            logger.info("Визуализатор остановлен")
        
        # Останавливаем торговую систему
        await session_controller.stop()
        logger.info("Торговая система остановлена")


if __name__ == "__main__":
    asyncio.run(main())
