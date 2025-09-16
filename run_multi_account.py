#!/usr/bin/env python3
"""
Запускатель многоаккаунтного торгового робота
"""
import asyncio
import sys
import os
import argparse
import json
import signal
import time
from pathlib import Path
from typing import List, Dict

# Добавляем корневую папку проекта в путь
sys.path.insert(0, str(Path(__file__).parent))

from robotlib.multiprocess.process_manager import ProcessManager
from robotlib.multiprocess.account_config import AccountConfig
from robotlib.utils.logger import get_logger


class MultiAccountRunner:
    """Основной запускатель для многоаккаунтной торговой системы"""
    
    def __init__(self):
        self._process_manager = ProcessManager()
        self._logger = get_logger(__name__)
        self._shutdown_requested = False
    
    def load_accounts_from_config(self, config_file: str) -> bool:
        """Загрузить конфигурации счетов из JSON файла"""
        try:
            if not os.path.exists(config_file):
                self._logger.error(f"Файл конфигурации не найден: {config_file}")
                return False
            
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            accounts = config_data.get('accounts', [])
            
            if not accounts:
                self._logger.error("В файле конфигурации не найдено счетов")
                return False
            
            success_count = 0
            base_port = 8050
            
            for i, account_data in enumerate(accounts):
                try:
                    # Создаём конфигурацию счёта
                    account_config = AccountConfig(
                        account_id=account_data['account_id'],
                        token=account_data['token'],
                        sandbox_token=account_data.get('sandbox_token', ''),
                        figi=account_data.get('figi', 'FUTIMOEXF000'),
                        deposit=account_data.get('deposit', 100000.0),
                        max_daily_loss=account_data.get('max_daily_loss', 5000.0),
                        max_position_size=account_data.get('max_position_size', 50000.0),
                        enable_visualization=account_data.get('enable_visualization', True),
                        visualization_port=account_data.get('visualization_port', base_port + i),
                        process_name=account_data.get('process_name', f"robot_{i+1}")
                    )
                    
                    if self._process_manager.add_account(account_config):
                        success_count += 1
                        self._logger.info(f"Добавлен счёт {account_config.account_id}")
                    else:
                        self._logger.error(f"Не удалось добавить счёт {account_data['account_id']}")
                        
                except Exception as e:
                    self._logger.error(f"Ошибка обработки счёта {account_data.get('account_id', 'unknown')}: {e}")
            
            self._logger.info(f"Загружено {success_count}/{len(accounts)} счетов")
            return success_count > 0
            
        except Exception as e:
            self._logger.error(f"Ошибка загрузки файла конфигурации: {e}")
            return False
    
    def add_single_account(
        self,
        account_id: str,
        token: str,
        sandbox_token: str = "",
        figi: str = "FUTIMOEXF000",
        port: int = 8050
    ) -> bool:
        """Добавить один счёт для тестирования"""
        try:
            account_config = AccountConfig(
                account_id=account_id,
                token=token,
                sandbox_token=sandbox_token,
                figi=figi,
                visualization_port=port
            )
            
            return self._process_manager.add_account(account_config)
            
        except Exception as e:
            self._logger.error(f"Ошибка добавления одного счёта: {e}")
            return False
    
    def setup_signal_handlers(self):
        """Настроить обработчики сигналов для корректной остановки"""
        def signal_handler(signum, frame):
            self._logger.info(f"Получен сигнал {signum}, инициируется остановка...")
            self._shutdown_requested = True
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
    
    def run_interactive_mode(self):
        """Запустить в интерактивном режиме с командной строкой"""
        self._logger.info("Запуск интерактивного режима...")
        self._logger.info("Введите 'help' для просмотра доступных команд")
        
        while not self._shutdown_requested:
            try:
                command = input("\n> ").strip().lower()
                
                if command == 'help':
                    self._print_help()
                elif command == 'status':
                    self._process_manager.print_status()
                elif command == 'start':
                    self._process_manager.start_all()
                elif command == 'stop':
                    self._process_manager.stop_all()
                elif command.startswith('start '):
                    account_id = command[6:].strip()
                    self._process_manager.start_account(account_id)
                elif command.startswith('stop '):
                    account_id = command[5:].strip()
                    self._process_manager.stop_account(account_id)
                elif command.startswith('restart '):
                    account_id = command[8:].strip()
                    self._process_manager.restart_account(account_id)
                elif command in ['quit', 'exit']:
                    self._shutdown_requested = True
                elif command == '':
                    continue
                else:
                    print(f"Неизвестная команда: {command}")
                    
            except KeyboardInterrupt:
                self._shutdown_requested = True
            except EOFError:
                self._shutdown_requested = True
            except Exception as e:
                self._logger.error(f"Ошибка в интерактивном режиме: {e}")
        
        self._logger.info("Выход из интерактивного режима...")
    
    def run_daemon_mode(self):
        """Запустить в режиме daemon (неинтерактивный)"""
        self._logger.info("Запуск режима daemon...")
        
        # Запустить всех роботов
        if not self._process_manager.start_all():
            self._logger.error("Не удалось запустить всех роботов")
            return False
        
        # Ожидаем сигнала остановки
        try:
            restart_backoff: Dict[str, float] = {}
            while not self._shutdown_requested:
                time.sleep(1)
                
                # Проверить, не умерли ли роботы неожиданно
                status = self._process_manager.get_status()
                for account_id, robot_status in status.items():
                    if not robot_status['is_running']:
                        now = time.time()
                        next_attempt = restart_backoff.get(account_id, 0)
                        if now >= next_attempt:
                            self._logger.warning(
                                f"Робот для счёта {account_id} не запущен, пробуем перезапустить"
                            )
                            if self._process_manager.restart_account(account_id):
                                # Успех — сбрасываем бэкофф
                                restart_backoff[account_id] = now + 2
                            else:
                                # Увеличиваем интервал (простой линейный бэкофф)
                                restart_backoff[account_id] = now + 10
                        
        except KeyboardInterrupt:
            self._logger.info("Запрошена остановка")
        
        return True
    
    def shutdown(self):
        """Корректная остановка"""
        self._logger.info("Остановка всех роботов...")
        self._process_manager.stop_all()
        self._logger.info("Остановка завершена")
    
    @property
    def process_manager(self) -> ProcessManager:
        """Получить менеджер процессов"""
        return self._process_manager
    
    def is_shutdown_requested(self) -> bool:
        """Проверить, запрошена ли остановка"""
        return self._shutdown_requested
    
    def _print_help(self):
        """Вывести справочную информацию"""
        print("\nДоступные команды:")
        print("  help                 - Показать эту справку")
        print("  status               - Показать статус всех роботов")
        print("  start                - Запустить всех роботов")
        print("  stop                 - Остановить всех роботов")
        print("  start <account_id>   - Запустить конкретного робота")
        print("  stop <account_id>    - Остановить конкретного робота")
        print("  restart <account_id> - Перезапустить конкретного робота")
        print("  quit/exit            - Выйти из программы")


def create_sample_config():
    """Создать пример файла конфигурации"""
    sample_config = {
        "accounts": [
            {
                "account_id": "account_1_id_here",
                "token": "your_token_here",
                "sandbox_token": "your_sandbox_token_here",
                "figi": "FUTIMOEXF000",
                "deposit": 100000.0,
                "max_daily_loss": 5000.0,
                "enable_visualization": True,
                "visualization_port": 8050,
                "process_name": "robot_main"
            },
            {
                "account_id": "account_2_id_here", 
                "token": "your_token_here",
                "sandbox_token": "your_sandbox_token_here",
                "figi": "SBER",
                "deposit": 50000.0,
                "max_daily_loss": 2500.0,
                "enable_visualization": True,
                "visualization_port": 8051,
                "process_name": "robot_sber"
            }
        ]
    }
    
    config_file = "accounts_config.json"
    with open(config_file, 'w') as f:
        json.dump(sample_config, f, indent=2)
    
    print(f"Пример конфигурации создан: {config_file}")
    print("Отредактируйте этот файл с реальными учётными данными")


def main():
    """Основная функция с разбором аргументов"""
    parser = argparse.ArgumentParser(description="Запускатель многоаккаунтного торгового робота")
    
    parser.add_argument(
        "--config",
        help="JSON файл конфигурации с данными счетов"
    )
    parser.add_argument(
        "--create-config",
        action="store_true",
        help="Создать пример файла конфигурации"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Запустить в интерактивном режиме (по умолчанию для файла конфигурации)"
    )
    parser.add_argument(
        "--daemon",
        action="store_true", 
        help="Запустить в режиме daemon (неинтерактивный)"
    )
    
    # Режим одного счёта (для быстрого тестирования)
    parser.add_argument(
        "--account-id",
        help="ID одного счёта для тестирования"
    )
    parser.add_argument(
        "--token",
        help="Токен одного счёта для тестирования"
    )
    parser.add_argument(
        "--sandbox-token",
        default="",
        help="Sandbox токен одного счёта для тестирования"
    )
    parser.add_argument(
        "--figi",
        default="FUTIMOEXF000",
        help="FIGI для тестирования одного счёта"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8050,
        help="Порт визуализации для одного счёта"
    )
    
    args = parser.parse_args()
    
    # Создать пример конфигурации
    if args.create_config:
        create_sample_config()
        return
    
    # Создать запускатель
    runner = MultiAccountRunner()
    runner.setup_signal_handlers()
    
    try:
        # Загрузить счета
        if args.config:
            # Загрузить из файла конфигурации
            if not runner.load_accounts_from_config(args.config):
                print("Не удалось загрузить счета из файла конфигурации")
                return 1
        elif args.account_id and args.token:
            # Режим одного счёта
            if not runner.add_single_account(
                args.account_id,
                args.token,
                args.sandbox_token,
                args.figi,
                args.port
            ):
                print("Не удалось добавить один счёт")
                return 1
        else:
            print("Необходимо указать либо --config, либо --account-id и --token")
            print("Используйте --create-config для создания примера файла конфигурации")
            return 1
        
        # Режим запуска
        if args.daemon:
            success = runner.run_daemon_mode()
        else:
            # По умолчанию интерактивный режим
            runner.run_interactive_mode()
            success = True
        
        return 0 if success else 1
        
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Критическая ошибка: {e}")
        return 1
    
    finally:
        runner.shutdown()


if __name__ == "__main__":
    sys.exit(main())