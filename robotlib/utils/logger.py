#!/usr/bin/env python3
"""
Простая утилита для настройки логирования
"""
import logging
import sys
import os
from typing import Optional


class ColorFormatter(logging.Formatter):
    """Добавляет цвета для вывода в консоль по уровню лога.
    DEBUG/INFO — белый, WARNING — жёлтый, ERROR/CRITICAL — красный.
    Файловый лог остаётся без цветов.
    """

    COLOR_RESET = "\033[0m"
    LEVEL_COLOR = {
        logging.DEBUG: "\033[37m",     # white
        logging.INFO: "\033[37m",      # white
        logging.WARNING: "\033[33m",   # yellow
        logging.ERROR: "\033[31m",     # red
        logging.CRITICAL: "\033[31m",  # red
    }

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        color = self.LEVEL_COLOR.get(record.levelno)
        # Раскрашиваем только интерактивную консоль
        if color and sys.stdout and hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
            return f"{color}{base}{self.COLOR_RESET}"
        return base


def setup_logging(level: int = logging.INFO, log_file: Optional[str] = None) -> None:
    """
    Настройка логирования для приложения
    
    Args:
        level: Уровень логирования
        log_file: Путь к файлу логов (опционально)
    """
    # Настраиваем основной логгер
    logger = logging.getLogger('investRobot')
    logger.setLevel(level)
    # Не пускать сообщения вверх к root-логгеру (исключает дублирование)
    logger.propagate = False
    
    # Очищаем существующие обработчики
    logger.handlers.clear()
    
    # Настраиваем форматы
    plain_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    color_formatter = ColorFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Консольный обработчик
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(color_formatter)
    logger.addHandler(console_handler)
    
    # Файловый обработчик (если указан)
    if log_file:
        # Создаем директорию для логов, если её нет
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(plain_formatter)
        logger.addHandler(file_handler)
    
    # Подавляем логи от внешних библиотек
    _suppress_external_logs()


def _suppress_external_logs():
    """Подавление логов от внешних библиотек"""
    external_loggers = [
        'werkzeug', 'dash', 'tinkoff.invest.logging', 'urllib3',
        'requests', 'matplotlib', 'plotly', 'pandas', 'numpy'
    ]
    
    for logger_name in external_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def get_logger(name: str = None) -> logging.Logger:
    """
    Получение логгера для конкретного модуля
    
    Args:
        name: Имя модуля (если None, возвращается основной логгер)
        
    Returns:
        Настроенный логгер
    """
    if name:
        return logging.getLogger(f'investRobot.{name}')
    return logging.getLogger('investRobot')


# Экспорт основных функций
__all__ = [
    'setup_logging',
    'get_logger'
]

