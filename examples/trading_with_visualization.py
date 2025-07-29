#!/usr/bin/env python3
"""
Пример торговли с визуализацией
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую папку проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from robotlib.trading.trading_config import TradingConfig
from robotlib.trading.visualizer_factory import TradingVisualizerFactory
from robotlib.trading.session_controller import SessionController
from robotlib.di.service_locator import ServiceLocator
from robotlib.utils.logger import get_logger


async def main():
    """Главная функция"""
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
        
        # Здесь должна быть инициализация всех зависимостей
        # Для примера создаем мок-зависимости
        logger.info("Инициализация зависимостей...")
        
        # Создаем контроллер сессии с визуализатором
        session_controller = SessionController(
            config=config,
            dependencies=None,  # Здесь должны быть реальные зависимости
            visualizer=visualizer
        )
        
        logger.info("Торговая система с визуализацией готова к запуску")
        logger.info("Визуализатор будет доступен по адресу: http://127.0.0.1:8050")
        
        # Запускаем сессию
        success = await session_controller.start()
        if success:
            logger.info("Торговая сессия запущена успешно")
            
            # Здесь должен быть основной цикл торговли
            # Для примера просто ждем
            await asyncio.sleep(10)
            
            # Останавливаем сессию
            await session_controller.stop()
            logger.info("Торговая сессия остановлена")
        else:
            logger.error("Не удалось запустить торговую сессию")
    
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
