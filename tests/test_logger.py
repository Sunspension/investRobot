#!/usr/bin/env python3
"""
Тесты для logger утилиты
"""
import logging
import os
import sys
import tempfile
import pytest
from unittest.mock import patch, Mock
from robotlib.utils.logger import (
    ColorFormatter, setup_logging, get_logger, _suppress_external_logs
)


class TestColorFormatter:
    """Тесты для класса ColorFormatter"""
    
    def test_color_formatter_initialization(self):
        """Тест инициализации ColorFormatter"""
        formatter = ColorFormatter("%(levelname)s - %(message)s")
        assert formatter is not None
        assert formatter.COLOR_RESET == "\033[0m"
        assert logging.DEBUG in formatter.LEVEL_COLOR
        assert logging.INFO in formatter.LEVEL_COLOR
        assert logging.WARNING in formatter.LEVEL_COLOR
        assert logging.ERROR in formatter.LEVEL_COLOR
        assert logging.CRITICAL in formatter.LEVEL_COLOR
    
    def test_color_formatter_colors(self):
        """Тест цветов для разных уровней"""
        formatter = ColorFormatter("%(levelname)s - %(message)s")
        
        # Проверяем цвета
        assert formatter.LEVEL_COLOR[logging.DEBUG] == "\033[37m"    # white
        assert formatter.LEVEL_COLOR[logging.INFO] == "\033[37m"     # white
        assert formatter.LEVEL_COLOR[logging.WARNING] == "\033[33m"  # yellow
        assert formatter.LEVEL_COLOR[logging.ERROR] == "\033[31m"    # red
        assert formatter.LEVEL_COLOR[logging.CRITICAL] == "\033[31m" # red
    
    def test_format_with_tty(self):
        """Тест форматирования с TTY (интерактивная консоль)"""
        formatter = ColorFormatter("%(levelname)s - %(message)s")
        
        # Создаем мок LogRecord
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        # Мокируем sys.stdout как TTY
        mock_stdout = Mock()
        mock_stdout.isatty.return_value = True
        
        with patch('sys.stdout', mock_stdout):
            result = formatter.format(record)
            assert "\033[37m" in result  # INFO color
            assert "\033[0m" in result   # Reset color
            assert "INFO - Test message" in result
    
    def test_format_without_tty(self):
        """Тест форматирования без TTY (не интерактивная консоль)"""
        formatter = ColorFormatter("%(levelname)s - %(message)s")
        
        # Создаем мок LogRecord
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="Test warning",
            args=(),
            exc_info=None
        )
        
        # Мокируем sys.stdout как не-TTY
        mock_stdout = Mock()
        mock_stdout.isatty.return_value = False
        
        with patch('sys.stdout', mock_stdout):
            result = formatter.format(record)
            assert "\033[33m" not in result  # WARNING color не должен быть
            assert "\033[0m" not in result   # Reset color не должен быть
            assert "WARNING - Test warning" in result
    
    def test_format_with_no_stdout(self):
        """Тест форматирования когда sys.stdout отсутствует"""
        formatter = ColorFormatter("%(levelname)s - %(message)s")
        
        # Создаем мок LogRecord
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Test error",
            args=(),
            exc_info=None
        )
        
        # Мокируем отсутствие sys.stdout
        with patch('sys.stdout', None):
            result = formatter.format(record)
            assert "\033[31m" not in result  # ERROR color не должен быть
            assert "\033[0m" not in result   # Reset color не должен быть
            assert "ERROR - Test error" in result
    
    def test_format_with_stdout_no_isatty(self):
        """Тест форматирования когда sys.stdout не имеет isatty"""
        formatter = ColorFormatter("%(levelname)s - %(message)s")
        
        # Создаем мок LogRecord
        record = logging.LogRecord(
            name="test",
            level=logging.CRITICAL,
            pathname="",
            lineno=0,
            msg="Test critical",
            args=(),
            exc_info=None
        )
        
        # Мокируем sys.stdout без isatty
        mock_stdout = Mock(spec=[])  # Пустой spec означает отсутствие isatty
        
        with patch('sys.stdout', mock_stdout):
            result = formatter.format(record)
            assert "\033[31m" not in result  # CRITICAL color не должен быть
            assert "\033[0m" not in result   # Reset color не должен быть
            assert "CRITICAL - Test critical" in result
    
    def test_format_different_levels(self):
        """Тест форматирования для разных уровней логирования"""
        formatter = ColorFormatter("%(levelname)s - %(message)s")
        
        # Мокируем sys.stdout как TTY
        mock_stdout = Mock()
        mock_stdout.isatty.return_value = True
        
        with patch('sys.stdout', mock_stdout):
            # DEBUG
            record = logging.LogRecord("test", logging.DEBUG, "", 0, "Debug msg", (), None)
            result = formatter.format(record)
            assert "\033[37m" in result  # white
            
            # WARNING
            record = logging.LogRecord("test", logging.WARNING, "", 0, "Warning msg", (), None)
            result = formatter.format(record)
            assert "\033[33m" in result  # yellow
            
            # ERROR
            record = logging.LogRecord("test", logging.ERROR, "", 0, "Error msg", (), None)
            result = formatter.format(record)
            assert "\033[31m" in result  # red


class TestSetupLogging:
    """Тесты для функции setup_logging"""
    
    def test_setup_logging_basic(self):
        """Тест базовой настройки логирования"""
        # Очищаем логгер перед тестом
        logger = logging.getLogger('investRobot')
        logger.handlers.clear()
        
        setup_logging()
        
        # Проверяем что логгер настроен
        assert logger.level == logging.INFO
        assert not logger.propagate
        assert len(logger.handlers) == 1  # Только консольный обработчик
        
        # Проверяем что обработчик настроен правильно
        handler = logger.handlers[0]
        assert isinstance(handler, logging.StreamHandler)
        assert handler.stream == sys.stdout
        assert handler.level == logging.INFO
        assert isinstance(handler.formatter, ColorFormatter)
    
    def test_setup_logging_with_custom_level(self):
        """Тест настройки логирования с кастомным уровнем"""
        logger = logging.getLogger('investRobot')
        logger.handlers.clear()
        
        setup_logging(level=logging.DEBUG)
        
        assert logger.level == logging.DEBUG
        handler = logger.handlers[0]
        assert handler.level == logging.DEBUG
    
    def test_setup_logging_with_log_file(self):
        """Тест настройки логирования с файлом"""
        logger = logging.getLogger('investRobot')
        logger.handlers.clear()
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            log_file = f.name
        
        try:
            setup_logging(log_file=log_file)
            
            # Проверяем что есть два обработчика
            assert len(logger.handlers) == 2  # Консольный + файловый
            
            # Проверяем файловый обработчик
            file_handler = None
            for handler in logger.handlers:
                if isinstance(handler, logging.FileHandler):
                    file_handler = handler
                    break
            
            assert file_handler is not None
            assert file_handler.baseFilename == log_file
            assert file_handler.level == logging.INFO
            assert isinstance(file_handler.formatter, logging.Formatter)  # Не ColorFormatter
        
        finally:
            os.unlink(log_file)
    
    def test_setup_logging_with_log_file_and_custom_level(self):
        """Тест настройки логирования с файлом и кастомным уровнем"""
        logger = logging.getLogger('investRobot')
        logger.handlers.clear()
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            log_file = f.name
        
        try:
            setup_logging(level=logging.WARNING, log_file=log_file)
            
            assert logger.level == logging.WARNING
            
            # Проверяем что оба обработчика имеют правильный уровень
            for handler in logger.handlers:
                assert handler.level == logging.WARNING
        
        finally:
            os.unlink(log_file)
    
    def test_setup_logging_clears_existing_handlers(self):
        """Тест что setup_logging очищает существующие обработчики"""
        logger = logging.getLogger('investRobot')
        
        # Очищаем все обработчики перед тестом
        logger.handlers.clear()
        
        # Добавляем старый обработчик
        old_handler = logging.StreamHandler()
        logger.addHandler(old_handler)
        assert len(logger.handlers) == 1
        
        # Настраиваем логирование
        setup_logging()
        
        # Проверяем что старый обработчик удален
        assert len(logger.handlers) == 1
        assert logger.handlers[0] != old_handler
    
    def test_setup_logging_creates_log_directory(self):
        """Тест что setup_logging создает директорию для логов"""
        logger = logging.getLogger('investRobot')
        logger.handlers.clear()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = os.path.join(temp_dir, "subdir", "test.log")
            
            # Директория subdir не существует
            assert not os.path.exists(os.path.dirname(log_file))
            
            setup_logging(log_file=log_file)
            
            # Директория должна быть создана
            assert os.path.exists(os.path.dirname(log_file))
            
            # Проверяем что файловый обработчик создан
            file_handler = None
            for handler in logger.handlers:
                if isinstance(handler, logging.FileHandler):
                    file_handler = handler
                    break
            
            assert file_handler is not None
            assert file_handler.baseFilename == log_file
    
    def test_setup_logging_with_existing_log_directory(self):
        """Тест что setup_logging работает с существующей директорией"""
        logger = logging.getLogger('investRobot')
        logger.handlers.clear()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = os.path.join(temp_dir, "test.log")
            
            # Директория уже существует
            assert os.path.exists(temp_dir)
            
            setup_logging(log_file=log_file)
            
            # Проверяем что файловый обработчик создан
            file_handler = None
            for handler in logger.handlers:
                if isinstance(handler, logging.FileHandler):
                    file_handler = handler
                    break
            
            assert file_handler is not None
            assert file_handler.baseFilename == log_file


class TestSuppressExternalLogs:
    """Тесты для функции _suppress_external_logs"""
    
    def test_suppress_external_logs(self):
        """Тест подавления логов от внешних библиотек"""
        # Проверяем что внешние логгеры настроены на WARNING
        external_loggers = [
            'werkzeug', 'dash', 'tinkoff.invest.logging', 'urllib3',
            'requests', 'matplotlib', 'plotly', 'pandas', 'numpy'
        ]
        
        for logger_name in external_loggers:
            logger = logging.getLogger(logger_name)
            assert logger.level == logging.WARNING
    
    def test_suppress_external_logs_called_by_setup_logging(self):
        """Тест что _suppress_external_logs вызывается setup_logging"""
        # Сбрасываем уровни внешних логгеров
        external_loggers = ['werkzeug', 'dash', 'urllib3']
        for logger_name in external_loggers:
            logging.getLogger(logger_name).setLevel(logging.DEBUG)
        
        # Вызываем setup_logging
        setup_logging()
        
        # Проверяем что уровни сброшены на WARNING
        for logger_name in external_loggers:
            logger = logging.getLogger(logger_name)
            assert logger.level == logging.WARNING


class TestGetLogger:
    """Тесты для функции get_logger"""
    
    def test_get_logger_without_name(self):
        """Тест получения основного логгера без имени"""
        logger = get_logger()
        
        assert logger.name == 'investRobot'
        assert isinstance(logger, logging.Logger)
    
    def test_get_logger_with_name(self):
        """Тест получения логгера с именем модуля"""
        logger = get_logger('test.module')
        
        assert logger.name == 'investRobot.test.module'
        assert isinstance(logger, logging.Logger)
    
    def test_get_logger_with_none_name(self):
        """Тест получения логгера с None именем"""
        logger = get_logger(None)
        
        assert logger.name == 'investRobot'
        assert isinstance(logger, logging.Logger)
    
    def test_get_logger_with_empty_name(self):
        """Тест получения логгера с пустым именем"""
        logger = get_logger('')
        
        # Пустая строка должна обрабатываться как None
        assert logger.name == 'investRobot'
        assert isinstance(logger, logging.Logger)
    
    def test_get_logger_multiple_calls_same_name(self):
        """Тест что множественные вызовы с одинаковым именем возвращают тот же объект"""
        logger1 = get_logger('test.module')
        logger2 = get_logger('test.module')
        
        assert logger1 is logger2  # Должен быть тот же объект
    
    def test_get_logger_different_names(self):
        """Тест что разные имена возвращают разные логгеры"""
        logger1 = get_logger('module1')
        logger2 = get_logger('module2')
        
        assert logger1 is not logger2
        assert logger1.name == 'investRobot.module1'
        assert logger2.name == 'investRobot.module2'


class TestLoggerIntegration:
    """Интеграционные тесты для логгера"""
    
    def test_logger_actually_logs(self):
        """Тест что логгер действительно выводит сообщения"""
        logger = logging.getLogger('investRobot')
        logger.handlers.clear()
        
        # Создаем мок для потока
        mock_stream = Mock()
        
        # Настраиваем простой обработчик для тестирования
        handler = logging.StreamHandler(mock_stream)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        
        # Логируем сообщение
        logger.info("Test message")
        
        # Проверяем что write был вызван
        mock_stream.write.assert_called()
    
    def test_color_formatter_integration(self):
        """Тест интеграции ColorFormatter с реальным логированием"""
        logger = logging.getLogger('investRobot')
        logger.handlers.clear()
        
        # Создаем мок для потока
        mock_stream = Mock()
        
        # Настраиваем обработчик с ColorFormatter
        handler = logging.StreamHandler(mock_stream)
        handler.setLevel(logging.INFO)
        formatter = ColorFormatter("%(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        # Мокируем sys.stdout как TTY (ColorFormatter проверяет sys.stdout)
        mock_stdout = Mock()
        mock_stdout.isatty.return_value = True
        
        with patch('sys.stdout', mock_stdout):
            # Логируем сообщение
            logger.info("Test message")
            
            # Проверяем что write был вызван с цветным сообщением
            mock_stream.write.assert_called()
            call_args = mock_stream.write.call_args[0][0]
            assert "\033[37m" in call_args  # INFO color
            assert "\033[0m" in call_args   # Reset color
            assert "INFO - Test message" in call_args
    
    def test_file_logging_integration(self):
        """Тест интеграции файлового логирования"""
        logger = logging.getLogger('investRobot')
        logger.handlers.clear()
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            log_file = f.name
        
        try:
            # Настраиваем файловый обработчик
            handler = logging.FileHandler(log_file, encoding='utf-8')
            handler.setLevel(logging.INFO)
            formatter = logging.Formatter("%(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            
            # Логируем сообщение
            logger.info("Test file message")
            logger.handlers[0].close()  # Закрываем обработчик
            
            # Проверяем что сообщение записалось в файл
            with open(log_file, 'r', encoding='utf-8') as f:
                content = f.read()
                assert "INFO - Test file message" in content
        
        finally:
            os.unlink(log_file)
