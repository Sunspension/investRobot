"""
Реализация индивидуального процесса робота
"""
import asyncio
import multiprocessing
import os
import signal
import sys
import time
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from robotlib.multiprocess.account_config import AccountConfig
from robotlib.trading.trading_config import TradingConfig
from robotlib.trading.di_container import TradingSystemContainer
from robotlib.utils.logger import get_logger, setup_logging


class RobotProcess:
    """Индивидуальный процесс робота для одного счёта"""
    
    def __init__(self, account_config: AccountConfig):
        self._account_config = account_config
        self._process: Optional[multiprocessing.Process] = None
        self._logger = get_logger(__name__)
        self._stop_event = multiprocessing.Event()
    
    def start(self) -> bool:
        """Запустить процесс робота"""
        if self.is_running():
            self._logger.warning(f"Процесс {self._account_config.get_process_name()} уже запущен")
            return False
        
        try:
            self._account_config.validate()
            
            # Создаём и запускаем процесс
            self._process = multiprocessing.Process(
                target=self._run_robot,
                name=self._account_config.get_process_name(),
                args=(self._account_config, self._stop_event)
            )
            
            self._process.start()
            self._logger.info(f"Запущен процесс робота {self._account_config.get_process_name()} (PID: {self._process.pid})")
            return True
            
        except Exception as e:
            self._logger.error(f"Не удалось запустить процесс робота: {e}")
            return False
    
    def stop(self, timeout: float = 30.0) -> bool:
        """Остановить процесс робота"""
        if not self.is_running():
            self._logger.info(f"Процесс {self._account_config.get_process_name()} не запущен")
            return True
        
        try:
            self._logger.info(f"Остановка процесса робота {self._account_config.get_process_name()}")
            
            # Подаём сигнал процессу о корректной остановке
            self._stop_event.set()
            
            # Ожидаем корректной остановки
            self._process.join(timeout=timeout)
            
            if self._process.is_alive():
                self._logger.warning(f"Процесс {self._account_config.get_process_name()} не остановился корректно, принудительно завершаем")
                self._process.terminate()
                self._process.join(timeout=5.0)
                
                if self._process.is_alive():
                    self._logger.error(f"Принудительно убиваем процесс {self._account_config.get_process_name()}")
                    self._process.kill()
                    self._process.join()
            
            self._logger.info(f"Процесс робота {self._account_config.get_process_name()} остановлен")
            return True
            
        except Exception as e:
            self._logger.error(f"Ошибка при остановке процесса робота: {e}")
            return False
    
    def restart(self) -> bool:
        """Перезапустить процесс робота"""
        self._logger.info(f"Перезапуск процесса робота {self._account_config.get_process_name()}")
        
        if not self.stop():
            return False
        
        # Немного ждём перед перезапуском
        time.sleep(2)
        
        return self.start()
    
    def is_running(self) -> bool:
        """Проверить, запущен ли процесс робота"""
        return self._process is not None and self._process.is_alive()
    
    def get_pid(self) -> Optional[int]:
        """Получить PID процесса"""
        if self._process:
            return self._process.pid
        return None
    
    def get_status(self) -> dict:
        """Получить информацию о состоянии процесса"""
        return {
            'process_name': self._account_config.get_process_name(),
            'account_id': self._account_config.account_id,
            'figi': self._account_config.figi,
            'is_running': self.is_running(),
            'pid': self.get_pid(),
            'visualization_port': self._account_config.visualization_port,
            'visualization_url': f"http://{self._account_config.visualization_host}:{self._account_config.visualization_port}" if self._account_config.enable_visualization else None
        }
    
    @property
    def account_config(self) -> AccountConfig:
        """Получить конфигурацию счёта"""
        return self._account_config
    
    @staticmethod
    def _run_robot(account_config: AccountConfig, stop_event: multiprocessing.Event):
        """Основная функция выполнения робота (запускается в отдельном процессе)"""
        
        # Настраиваем обработчики сигналов для корректной остановки
        def signal_handler(signum, frame):
            stop_event.set()
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        # Создаём новый event loop для этого процесса
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Настраиваем per-account логирование в дочернем процессе
        try:
            # Преобразуем текстовый уровень в численный
            import logging
            level = getattr(logging, account_config.log_level.upper(), logging.INFO)
            setup_logging(level=level, log_file=account_config.get_log_file())
        except Exception:
            # В случае сбоя логирования не блокируем запуск
            pass

        try:
            # Запускаем робота
            loop.run_until_complete(RobotProcess._run_robot_async(account_config, stop_event))
        except Exception as e:
            logger = get_logger(__name__)
            logger.error(f"Критическая ошибка в процессе робота: {e}")
        finally:
            loop.close()
    
    @staticmethod
    async def _run_robot_async(account_config: AccountConfig, stop_event: multiprocessing.Event):
        """Асинхронное выполнение робота"""
        logger = get_logger(__name__)
        logger.info(f"Запуск робота для счёта {account_config.account_id}")
        
        try:
            # Создаём торговую конфигурацию
            trading_config = TradingConfig(
                figi=account_config.figi,
                auto_close_positions=account_config.auto_close_positions,
                end_of_day_close=account_config.end_of_day_close,
                close_time=account_config.close_time,
                enable_visualization=account_config.enable_visualization
            )
            
            # Добавляем учётные данные
            @dataclass
            class TCSClient:
                token: str
                account_id: str
                sandbox_token: str
            
            trading_config.tcs_client = TCSClient(
                token=account_config.token,
                account_id=account_config.account_id,
                sandbox_token=account_config.sandbox_token
            )
            
            # Создаём DI контейнер
            container = TradingSystemContainer(trading_config)
            
            # Собираем торговую систему с уникальным портом
            trading_system = await container.build_trading_system(
                host=account_config.visualization_host,
                port=account_config.visualization_port,
                start_server=account_config.enable_visualization
            )
            
            logger.info(f"Торговая система создана для счёта {account_config.account_id}")
            
            # Запускаем визуализатор, если включён
            if trading_system['visualizer'] and account_config.enable_visualization:
                await trading_system['visualizer'].start()
                logger.info(f"Визуализатор запущен на порту {account_config.visualization_port}")
            
            # Получаем контроллер сессии
            session_controller = trading_system['session_controller']
            
            # Запускаем торговую сессию
            if await session_controller.start():
                logger.info(f"Торговая сессия запущена для счёта {account_config.account_id}")
                
                # Основной торговый цикл
                while not stop_event.is_set():
                    try:
                        # Выполняем итерацию торгового цикла
                        await session_controller.run_trading_loop()
                        
                        # Проверяем, следует ли продолжать
                        if not session_controller.is_running:
                            logger.info("Торговая сессия остановлена внутренне")
                            break
                        
                        # Небольшая задержка для предотвращения активного ожидания
                        await asyncio.sleep(0.1)
                        
                    except asyncio.CancelledError:
                        logger.info("Торговый цикл отменён")
                        break
                    except Exception as e:
                        logger.error(f"Ошибка в торговом цикле: {e}")
                        # Продолжаем работу, если не запрошена остановка
                        if stop_event.is_set():
                            break
                        await asyncio.sleep(1)
            
            else:
                logger.error(f"Не удалось запустить торговую сессию для счёта {account_config.account_id}")
        
        except Exception as e:
            logger.error(f"Ошибка в выполнении робота: {e}")
        
        finally:
            logger.info(f"Остановка робота для счёта {account_config.account_id}")
            
            # Очистка
            try:
                if 'session_controller' in locals():
                    await session_controller.stop()
                
                if 'trading_system' in locals() and trading_system.get('visualizer'):
                    await trading_system['visualizer'].stop()
                    
            except Exception as e:
                logger.error(f"Ошибка при очистке: {e}")
            
            logger.info(f"Робот остановлен для счёта {account_config.account_id}")