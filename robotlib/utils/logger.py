#!/usr/bin/env python3
"""
Простая утилита для настройки логирования
"""
import logging
import sys
import os
from typing import Optional


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
    
    # Очищаем существующие обработчики
    logger.handlers.clear()
    
    # Настраиваем формат
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Консольный обработчик
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Файловый обработчик (если указан)
    if log_file:
        # Создаем директорию для логов, если её нет
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
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

