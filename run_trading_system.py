#!/usr/bin/env python3
"""
Единый entry point для запуска торговой системы
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
# EventBus убран из основной системы - используется только для визуализации
from robotlib.utils.logger import get_logger


def stop_previous_processes(port: int = 8050):
    """Останавливает предыдущие процессы на указанном порту"""
    logger = get_logger(__name__)
    
    try:
        # Находим все процессы Python
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            python_pids = []
            current_pid = os.getpid()
            
            for line in lines:
                if 'python' in line and 'run_trading_system.py' in line and 'grep' not in line:
                    parts = line.split()
                    if len(parts) > 1:
                        pid = parts[1]
                        try:
                            if int(pid) != current_pid:
                                python_pids.append(pid)
                        except ValueError:
                            # пропускаем строки, где PID не число
                            continue
            
            if python_pids:
                logger.info(f"🛑 Найдены процессы Python: {python_pids}")
                
                for pid in python_pids:
                    try:
                        # Отправляем SIGTERM
                        os.kill(int(pid), signal.SIGTERM)
                        logger.info(f"✅ Отправлен SIGTERM процессу {pid}")
                    except ProcessLookupError:
                        logger.info(f"⚠️ Процесс {pid} уже завершен")
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось остановить процесс {pid}: {e}")
                
                # Ждем немного
                import time
                time.sleep(2)
                
                # Проверяем, остались ли процессы
                result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    remaining_pids = []
                    
                    for line in lines:
                        if 'python' in line and 'run_trading_system.py' in line and 'grep' not in line:
                            parts = line.split()
                            if len(parts) > 1:
                                pid = parts[1]
                                try:
                                    if int(pid) != current_pid:
                                        remaining_pids.append(pid)
                                except ValueError:
                                    continue
                    
                    if remaining_pids:
                        logger.info(f"💀 Остались процессы: {remaining_pids}, отправляем SIGKILL")
                        for pid in remaining_pids:
                            try:
                                os.kill(int(pid), signal.SIGKILL)
                                logger.info(f"💀 Отправлен SIGKILL процессу {pid}")
                            except Exception as e:
                                logger.warning(f"⚠️ Не удалось убить процесс {pid}: {e}")
                    else:
                        logger.info("✅ Все процессы остановлены")
            else:
                logger.info("✅ Процессы Python не найдены")
        else:
            logger.warning("⚠️ Не удалось получить список процессов")
            
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при остановке процессов: {e}")


async def run_trading_system(
    figi: str = "FUTIMOEXF000",
    enable_visualization: bool = True,
    host: str = "127.0.0.1",
    port: int = 8050,
    start_server: bool = True
):
    """Запускает торговую систему с указанными параметрами"""
    
    logger = get_logger(__name__)
    logger.info("🚀 Запуск торговой системы")
    logger.info(f"📊 FIGI: {figi}")
    logger.info(f"📈 Визуализация: {'включена' if enable_visualization else 'отключена'}")
    if enable_visualization:
        logger.info(f"🌐 Веб-сервер: {'включен' if start_server else 'отключен'}")
    
    # Останавливаем предыдущие процессы
    if enable_visualization:
        logger.info(f"🌐 Визуализатор будет доступен по адресу: http://{host}:{port}")
        stop_previous_processes(port)
    
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
    logger.info(f"🚌 EventBus: {type(trading_system['event_bus']).__name__}")
    
    # Запускаем визуализатор (если включен и сервер нужен)
    if trading_system['visualizer'] and start_server:
        await trading_system['visualizer'].start()
        logger.info("✅ Dash визуализатор событий запущен")
    elif trading_system['visualizer']:
        logger.info("✅ Dash визуализатор готов к запуску (сервер отключен)")
    
    # EventBus убран из основной системы - используется только для визуализации
    # Логирование событий теперь происходит напрямую в компонентах
    
    # SignalManager больше не подписывается на события - работает напрямую
    
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
    parser.add_argument(
        "--no-server", 
        action="store_true", 
        help="Не запускать веб-сервер визуализатора (только для тестирования)"
    )
    
    args = parser.parse_args()
    
    # Запускаем торговую систему
    asyncio.run(run_trading_system(
        figi=args.figi,
        enable_visualization=not args.no_visualization,
        host=args.host,
        port=args.port,
        start_server=not args.no_server
    ))


if __name__ == "__main__":
    main()

