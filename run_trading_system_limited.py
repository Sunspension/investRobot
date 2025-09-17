#!/usr/bin/env python3
"""
Запуск торговой системы с ограниченным временем работы
"""
import asyncio
import sys
import os
import argparse
import subprocess
import signal
from typing import Optional

# Добавляем путь к модулю
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from robotlib.trading.di_container import TradingSystemContainer
from robotlib.trading.trading_config import TradingConfig
from robotlib.utils.logger import get_logger


async def run_trading_system_limited(
    figi: str = "FUTIMOEXF000",
    enable_visualization: bool = True,
    host: str = "127.0.0.1",
    port: int = 8050,
    start_server: bool = True,
    run_duration: int = 60  # Время работы в секундах
):
    """Запускает торговую систему с ограниченным временем работы"""
    
    logger = get_logger(__name__)
    logger.info("🚀 Запуск торговой системы (ограниченное время)")
    logger.info(f"📊 FIGI: {figi}")
    logger.info(f"📈 Визуализация: {'включена' if enable_visualization else 'отключена'}")
    logger.info(f"⏱️ Время работы: {run_duration} секунд")
    if enable_visualization:
        logger.info(f"🌐 Веб-сервер: {'включен' if start_server else 'отключен'}")
    
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
    container = TradingSystemContainer(trading_config)
    trading_system = await container.build_trading_system(host=host, port=port, start_server=start_server)
    
    logger.info("✅ Торговая система собрана через DI контейнер")
    
    # Запускаем визуализатор (если включен и сервер нужен)
    if trading_system['visualizer'] and start_server:
        await trading_system['visualizer'].start()
        logger.info("✅ Dash визуализатор событий запущен")
    elif trading_system['visualizer']:
        logger.info("✅ Dash визуализатор готов к запуску (сервер отключен)")
    
    # Получаем SessionController
    session_controller = trading_system['session_controller']
    
    logger.info("🎮 Запуск торговой сессии...")
    try:
        # Устанавливаем принудительный запуск
        session_controller._force_start = True
        
        success = await session_controller.start()
        logger.info(f"✅ Результат запуска: {success}")
        
        if success:
            logger.info("✅ Торговая сессия запущена успешно")
            if enable_visualization and start_server:
                logger.info(f"🌐 Визуализатор доступен по адресу: http://{host}:{port}")
            
            # Ждем ограниченное время вместо бесконечного цикла
            logger.info(f"⏱️ Работаем {run_duration} секунд...")
            for i in range(run_duration):
                await asyncio.sleep(1)
                if (i + 1) % 10 == 0:  # Логируем каждые 10 секунд
                    logger.info(f"⏱️ Прошло {i + 1}/{run_duration} секунд...")
            
            logger.info("⏱️ Время работы истекло, останавливаем систему...")
        else:
            logger.error("❌ Не удалось запустить торговую сессию")
        
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
    """Основная функция"""
    parser = argparse.ArgumentParser(description='Запуск торговой системы (ограниченное время)')
    parser.add_argument('--figi', default='FUTIMOEXF000', help='FIGI инструмента для торговли')
    parser.add_argument('--no-visualization', action='store_true', help='Отключить визуализацию')
    parser.add_argument('--host', default='127.0.0.1', help='Хост для визуализатора')
    parser.add_argument('--port', type=int, default=8050, help='Порт для визуализатора')
    parser.add_argument('--no-server', action='store_true', help='Не запускать веб-сервер визуализатора')
    parser.add_argument('--duration', type=int, default=60, help='Время работы в секундах (по умолчанию: 60)')
    
    args = parser.parse_args()
    
    try:
        asyncio.run(run_trading_system_limited(
            figi=args.figi,
            enable_visualization=not args.no_visualization,
            host=args.host,
            port=args.port,
            start_server=not args.no_server,
            run_duration=args.duration
        ))
    except KeyboardInterrupt:
        print("\n👋 Остановка по запросу пользователя")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
