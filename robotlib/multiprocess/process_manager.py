"""
Менеджер для нескольких процессов роботов
"""
import time
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

from robotlib.multiprocess.account_config import AccountConfig
from robotlib.multiprocess.robot_process import RobotProcess
from robotlib.utils.logger import get_logger


class ProcessManager:
    """Менеджер для нескольких процессов торговых роботов"""
    
    def __init__(self):
        self._robots: Dict[str, RobotProcess] = {}
        self._logger = get_logger(__name__)
    
    def add_account(self, account_config: AccountConfig) -> bool:
        """Добавить новый торговый счёт"""
        try:
            account_config.validate()
            
            account_key = account_config.account_id
            
            if account_key in self._robots:
                self._logger.warning(f"Счёт {account_key} уже существует")
                return False
            
            # Проверяем конфликты портов
            if self._is_port_in_use(account_config.visualization_port):
                new_port = self.get_next_available_port(start_port=account_config.visualization_port)
                self._logger.warning(
                    f"Порт {account_config.visualization_port} уже используется, переназначаем на {new_port}"
                )
                account_config.visualization_port = new_port
            
            robot = RobotProcess(account_config)
            self._robots[account_key] = robot
            
            self._logger.info(f"Добавлен счёт {account_key} с портом {account_config.visualization_port}")
            return True
            
        except Exception as e:
            self._logger.error(f"Не удалось добавить счёт: {e}")
            return False
    
    def remove_account(self, account_id: str) -> bool:
        """Удалить торговый счёт"""
        if account_id not in self._robots:
            self._logger.warning(f"Счёт {account_id} не найден")
            return False
        
        robot = self._robots[account_id]
        
        # Останавливаем робота, если он запущен
        if robot.is_running():
            if not robot.stop():
                self._logger.error(f"Не удалось остановить робота для счёта {account_id}")
                return False
        
        del self._robots[account_id]
        self._logger.info(f"Удалён счёт {account_id}")
        return True
    
    def start_account(self, account_id: str) -> bool:
        """Запустить торговлю для конкретного счёта"""
        if account_id not in self._robots:
            self._logger.error(f"Счёт {account_id} не найден")
            return False
        
        robot = self._robots[account_id]
        return robot.start()
    
    def stop_account(self, account_id: str) -> bool:
        """Остановить торговлю для конкретного счёта"""
        if account_id not in self._robots:
            self._logger.error(f"Счёт {account_id} не найден")
            return False
        
        robot = self._robots[account_id]
        return robot.stop()
    
    def restart_account(self, account_id: str) -> bool:
        """Перезапустить торговлю для конкретного счёта"""
        if account_id not in self._robots:
            self._logger.error(f"Счёт {account_id} не найден")
            return False
        
        robot = self._robots[account_id]
        return robot.restart()
    
    def start_all(self) -> bool:
        """Запустить всех роботов"""
        self._logger.info(f"Запуск всех {len(self._robots)} роботов")
        
        success_count = 0
        
        # Запускаем роботов с задержкой для избежания конфликтов ресурсов
        for account_id, robot in self._robots.items():
            if robot.start():
                success_count += 1
                self._logger.info(f"Запущен робот для счёта {account_id}")
                # Небольшая задержка между запусками
                time.sleep(2)
            else:
                self._logger.error(f"Не удалось запустить робота для счёта {account_id}")
        
        self._logger.info(f"Запущено {success_count}/{len(self._robots)} роботов")
        return success_count == len(self._robots)
    
    def stop_all(self, timeout: float = 30.0) -> bool:
        """Остановить всех роботов"""
        self._logger.info(f"Остановка всех {len(self._robots)} роботов")
        
        if not self._robots:
            self._logger.info("Нет роботов для остановки")
            return True

        success_count = 0
        
        # Используем ThreadPoolExecutor для параллельной остановки
        with ThreadPoolExecutor(max_workers=len(self._robots)) as executor:
            futures = {}
            
            for account_id, robot in self._robots.items():
                if robot.is_running():
                    future = executor.submit(robot.stop, timeout)
                    futures[future] = account_id
                else:
                    success_count += 1
            
            # Ожидаем завершения всех остановок
            for future in futures:
                account_id = futures[future]
                try:
                    if future.result():
                        success_count += 1
                        self._logger.info(f"Остановлен робот для счёта {account_id}")
                    else:
                        self._logger.error(f"Не удалось остановить робота для счёта {account_id}")
                except Exception as e:
                    self._logger.error(f"Ошибка остановки робота для счёта {account_id}: {e}")
        
        self._logger.info(f"Остановлено {success_count}/{len(self._robots)} роботов")
        return success_count == len(self._robots)
    
    def get_status(self) -> Dict[str, dict]:
        """Получить статус всех роботов"""
        status = {}
        
        for account_id, robot in self._robots.items():
            status[account_id] = robot.get_status()
        
        return status
    
    def get_running_accounts(self) -> List[str]:
        """Получить список ID запущенных счетов"""
        return [
            account_id for account_id, robot in self._robots.items()
            if robot.is_running()
        ]
    
    def get_stopped_accounts(self) -> List[str]:
        """Получить список ID остановленных счетов"""
        return [
            account_id for account_id, robot in self._robots.items()
            if not robot.is_running()
        ]
    
    def print_status(self) -> None:
        """Вывести подробный статус всех роботов"""
        print("\n" + "=" * 80)
        print("СТАТУС ТОРГОВЫХ РОБОТОВ")
        print("=" * 80)
        
        if not self.has_robots():
            print("Роботы не настроены")
            return
        
        status = self.get_status()
        
        for account_id, robot_status in status.items():
            print(f"\nСчёт: {account_id}")
            print(f"  Процесс: {robot_status['process_name']}")
            print(f"  FIGI: {robot_status['figi']}")
            print(f"  Статус: {'ЗАПУЩЕН' if robot_status['is_running'] else 'ОСТАНОВЛЕН'}")
            
            if robot_status['is_running']:
                print(f"  PID: {robot_status['pid']}")
            
            if robot_status['visualization_url']:
                print(f"  Визуализация: {robot_status['visualization_url']}")
        
        running_count = len(self.get_running_accounts())
        total_count = self.robots_count
        
        print(f"\nИтого: {running_count}/{total_count} роботов запущено")
        print("=" * 80)
    
    def _is_port_in_use(self, port: int) -> bool:
        """Проверить, используется ли порт другим роботом"""
        for robot in self._robots.values():
            if (robot.account_config.enable_visualization and 
                robot.account_config.visualization_port == port):
                return True
        return False
    
    def get_next_available_port(self, start_port: int = 8050) -> int:
        """Получить следующий доступный порт начиная с start_port"""
        port = start_port
        used_ports = set()
        
        # Собираем все используемые порты
        for robot in self._robots.values():
            if robot.account_config.enable_visualization:
                used_ports.add(robot.account_config.visualization_port)
        
        # Находим следующий доступный порт
        while port in used_ports:
            port += 1
        
        return port
    
    @property
    def robots_count(self) -> int:
        """Получить количество роботов"""
        return len(self._robots)
    
    def has_robots(self) -> bool:
        """Проверить, есть ли роботы"""
        return len(self._robots) > 0