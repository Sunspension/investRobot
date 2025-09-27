"""
Конфигурация логирования для визуализатора
"""
import logging
import warnings
import sys
from io import StringIO
import asyncio


class QuietFlaskServer:
    """Класс для отключения логов Flask сервера"""
    
    def __init__(self):
        self.original_stderr = sys.stderr
        self.original_stdout = sys.stdout
        self.quiet_stream = StringIO()
    
    def __enter__(self):
        # Перенаправляем stderr для подавления логов Flask
        sys.stderr = self.quiet_stream
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Восстанавливаем stderr
        sys.stderr = self.original_stderr
        sys.stdout = self.original_stdout


class _ColorFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[90m',     # grey
        'INFO': '\033[92m',      # green
        'WARNING': '\033[93m',   # yellow
        'ERROR': '\033[91m',     # red
        'CRITICAL': '\033[91m',  # red
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, '')
        message = super().format(record)
        if color and sys.stderr.isatty():
            return f"{color}{message}{self.RESET}"
        return message


def _ensure_color_console_handler(level=logging.INFO) -> logging.Handler:
    handler = logging.StreamHandler()
    date_format = "%Y-%m-%d %H:%M:%S"
    fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    handler.setFormatter(_ColorFormatter(fmt, datefmt=date_format))
    handler.setLevel(level)
    root = logging.getLogger()
    # Избегаем дублирования хендлеров при повторных вызовах
    if not any(isinstance(h, logging.StreamHandler) and isinstance(h.formatter, _ColorFormatter) for h in root.handlers):
        root.addHandler(handler)
    root.setLevel(min(root.level or level, level))
    return handler


def setup_asyncio_exception_logging(logger_name: str = __name__) -> None:
    """Перехватывает необработанные исключения asyncio и логирует их через наш форматтер."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return

    def _handler(loop, context):
        logger = logging.getLogger(logger_name)
        exc = context.get('exception')
        msg = context.get('message', 'Unhandled asyncio exception')
        logger.error(msg, exc_info=exc)

    try:
        loop.set_exception_handler(_handler)
    except Exception:
        pass


def disable_verbose_logging(enable_debug_logs=False):
    """
    Отключает избыточные логи Flask/Dash
    
    Args:
        enable_debug_logs: Если True, включает отладочные логи для нашего приложения
    """
    # Отключаем логи веб-сервера
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    logging.getLogger('dash').setLevel(logging.ERROR)
    logging.getLogger('flask').setLevel(logging.ERROR)
    logging.getLogger('urllib3').setLevel(logging.ERROR)
    logging.getLogger('tinkoff.invest.logging').setLevel(logging.ERROR)
    
    # Отключаем предупреждения
    warnings.filterwarnings("ignore", category=UserWarning, module="werkzeug")
    warnings.filterwarnings("ignore", category=UserWarning, module="dash")
    warnings.filterwarnings("ignore", category=UserWarning, module="flask")
    
    # Отключаем логи gRPC
    logging.getLogger('grpc').setLevel(logging.ERROR)
    logging.getLogger('grpc._cython').setLevel(logging.ERROR)
    
    if enable_debug_logs:
        # Включаем отладочные логи для нашего приложения
        logging.getLogger('visualization').setLevel(logging.INFO)
        logging.getLogger('robotlib').setLevel(logging.INFO)
        # Цветной хендлер для консоли
        h = _ensure_color_console_handler(level=logging.INFO)
        # Подключаем к asyncio логгеру тот же уровень/хендлер
        alog = logging.getLogger('asyncio')
        alog.setLevel(logging.ERROR)
        if not any(isinstance(x, logging.StreamHandler) and isinstance(getattr(x, 'formatter', None), _ColorFormatter) for x in alog.handlers):
            alog.addHandler(h)
        # Перехватчик необработанных исключений asyncio
        setup_asyncio_exception_logging(logger_name='robotlib.strategies.strategy_manager')
        print("🔍 Отладочные логи включены")
    else:
        # Отключаем все логи
        logging.getLogger('visualization').setLevel(logging.ERROR)
        logging.getLogger('robotlib').setLevel(logging.ERROR)
        print("🔇 Логи отключены")
