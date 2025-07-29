"""
Упрощенный класс для управления торговой сессией
"""
from robotlib.trading.interfaces import TradingDependencies
from robotlib.trading.session_interfaces import TradingSessionable
from robotlib.trading.session_controller import SessionController
from robotlib.trading.session_stats import SessionStats
from robotlib.trading.trading_config import TradingConfig
from robotlib.utils.logger import get_logger


class TradingSession(TradingSessionable):
    """Упрощенный класс для управления торговой сессией"""
    
    def __init__(
        self, 
        config: TradingConfig, 
        dependencies: TradingDependencies,
        force_start: bool = False
    ):
        """
        Инициализация торговой сессии
        
        Args:
            config: Конфигурация торговли
            dependencies: Готовые зависимости (обязательно)
            force_start: Принудительный запуск даже если рынок закрыт
        """
        self.config = config
        self.dependencies = dependencies
        self.force_start = force_start
        self.logger = get_logger(__name__)
        
        # Создаем контроллер сессии
        self.controller = SessionController(config, dependencies, force_start)
    
    async def start(self) -> bool:
        """Запускает торговую сессию"""
        return await self.controller.start()
    
    async def stop(self) -> None:
        """Останавливает торговую сессию"""
        await self.controller.stop()
    
    async def run_trading_loop(self) -> None:
        """Запускает основной торговый цикл"""
        await self.controller.run_trading_loop()
    
    def get_stats(self) -> dict:
        """Возвращает статистику сессии"""
        return self.controller.stats.get_stats_dict()
    
    def print_stats(self) -> None:
        """Выводит статистику в консоль"""
        self.controller.stats.print_stats()
    
    async def execute_signal(self, signal) -> None:
        """Выполняет торговый сигнал (для обратной совместимости)"""
        self.logger.warning("execute_signal устарел, используйте strategy_manager напрямую")
        # Этот метод оставлен для обратной совместимости
        # В новой архитектуре сигналы обрабатываются через strategy_manager
    
    async def get_session_status(self) -> dict:
        """Возвращает статус сессии"""
        return await self.controller.get_session_status()
    
    async def close_all_positions(self) -> None:
        """Закрывает все позиции"""
        await self.controller._close_all_positions()
