"""
Конфигурация логирования для визуализатора
"""
import logging
import warnings
import sys
from io import StringIO


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
        
        # Настраиваем базовый логгер
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        print("🔍 Отладочные логи включены")
    else:
        # Отключаем все логи
        logging.getLogger('visualization').setLevel(logging.ERROR)
        logging.getLogger('robotlib').setLevel(logging.ERROR)
        print("🔇 Логи отключены")
