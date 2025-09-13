"""
DI контейнер для торговой системы
"""
from typing import Optional, Dict, Any
from robotlib.utils.logger import get_logger
from robotlib.trading.event_bus_interface import EventBusable, EventBus, MockEventBus
from robotlib.trading.trading_config import TradingConfig
from robotlib.trading.interfaces import TradingDependencies
from robotlib.trading.session_controller import SessionController
from robotlib.trading.session_initializer import SessionInitializer
from robotlib.trading.session_stats import SessionStats
from robotlib.trading.portfolio_manager import PortfolioManager
from robotlib.trading.risk_manager import RiskManager
from robotlib.trading.order_executor import OrderExecutor
from robotlib.trading.market_data_stream import MarketDataStream
from robotlib.signal_manager import SignalManager
from robotlib.strategies.strategy_manager import StrategyManager
from robotlib.strategies.long import LongStrategy
from robotlib.strategies.short import ShortStrategy


class TradingSystemContainer:
    """DI контейнер для торговой системы"""
    
    def __init__(self, config: TradingConfig, enable_visualization: bool = False):
        self._config = config
        self._enable_visualization = enable_visualization
        self._logger = get_logger(__name__)
        self._instances: Dict[str, Any] = {}
    
    def get_event_bus(self) -> EventBusable:
        """Получает шину событий"""
        if 'event_bus' not in self._instances:
            if self._enable_visualization:
                self._instances['event_bus'] = EventBus()
            else:
                self._instances['event_bus'] = MockEventBus()
        return self._instances['event_bus']
    
    def get_session_stats(self) -> SessionStats:
        """Получает статистику сессии"""
        if 'session_stats' not in self._instances:
            self._instances['session_stats'] = SessionStats()
        return self._instances['session_stats']
    
    def get_portfolio_manager(self) -> PortfolioManager:
        """Получает менеджер портфеля"""
        if 'portfolio_manager' not in self._instances:
            self._instances['portfolio_manager'] = PortfolioManager(
                api_client=None  # Будет инжектирован позже
            )
        return self._instances['portfolio_manager']
    
    def get_risk_manager(self) -> RiskManager:
        """Получает менеджер рисков"""
        if 'risk_manager' not in self._instances:
            from robotlib.trading.risk_manager import RiskLimits
            self._instances['risk_manager'] = RiskManager(
                portfolio_manager=self.get_portfolio_manager(),
                risk_limits=RiskLimits(
                    max_daily_loss=50000.0,  # Дефолтное значение
                    max_position_size=100000.0  # Дефолтное значение
                )
            )
        return self._instances['risk_manager']
    
    def get_order_executor(self) -> OrderExecutor:
        """Получает исполнитель ордеров"""
        if 'order_executor' not in self._instances:
            self._instances['order_executor'] = OrderExecutor(
                api_client=None  # Будет инжектирован позже
            )
        return self._instances['order_executor']
    
    def get_signal_manager(self) -> SignalManager:
        """Получает менеджер сигналов"""
        if 'signal_manager' not in self._instances:
            self._instances['signal_manager'] = SignalManager()
        return self._instances['signal_manager']
    
    def get_strategy_manager(self) -> StrategyManager:
        """Получает менеджер стратегий"""
        if 'strategy_manager' not in self._instances:
            strategy_manager = StrategyManager(
                signal_manager=self.get_signal_manager(),
                risk_manager=self.get_risk_manager(),
                portfolio_manager=self.get_portfolio_manager()
            )
            
            # Стратегии добавляются автоматически в StrategyManager
            
            self._instances['strategy_manager'] = strategy_manager
        return self._instances['strategy_manager']
    
    def get_market_data_stream(self) -> MarketDataStream:
        """Получает стрим рыночных данных"""
        if 'market_data_stream' not in self._instances:
            self._instances['market_data_stream'] = MarketDataStream(
                api_client=None,  # Будет инжектирован позже
                figi=self._config.figi,
                signal_manager=self.get_signal_manager(),
                visualizer=None,  # Больше не нужен
                cache_size=1000,
                event_bus=self.get_event_bus()  # Передаем EventBus
            )
        return self._instances['market_data_stream']
    
    def get_trading_dependencies(self) -> TradingDependencies:
        """Получает зависимости торговой системы"""
        if 'trading_dependencies' not in self._instances:
            self._instances['trading_dependencies'] = TradingDependencies(
                api_client=None,  # Будет инжектирован позже
                session_stats=self.get_session_stats(),
                session_initializer=None,  # Будет установлен позже
                portfolio_manager=self.get_portfolio_manager(),
                risk_manager=self.get_risk_manager(),
                order_executor=self.get_order_executor(),
                market_data_stream=self.get_market_data_stream(),
                signal_manager=self.get_signal_manager(),
                strategy_manager=self.get_strategy_manager()
            )
        return self._instances['trading_dependencies']
    
    def get_session_initializer(self) -> SessionInitializer:
        """Получает инициализатор сессии"""
        if 'session_initializer' not in self._instances:
            dependencies = self.get_trading_dependencies()
            self._instances['session_initializer'] = SessionInitializer(
                config=self._config,
                dependencies=dependencies
            )
            # Устанавливаем обратную ссылку
            dependencies.session_initializer = self._instances['session_initializer']
        return self._instances['session_initializer']
    
    def get_session_controller(self) -> SessionController:
        """Получает контроллер сессии"""
        if 'session_controller' not in self._instances:
            # Сначала создаем session_initializer
            session_initializer = self.get_session_initializer()
            
            self._instances['session_controller'] = SessionController(
                config=self._config,
                dependencies=self.get_trading_dependencies(),
                force_start=False,
                visualizer=None  # Больше не нужен
            )
        return self._instances['session_controller']
    
    def get_visualizer(self) -> Optional[Any]:
        """Получает визуализатор (если включен)"""
        if not self._enable_visualization:
            return None
        
        if 'visualizer' not in self._instances:
            try:
                from visualization.dash_event_visualizer import DashEventVisualizer
                self._instances['visualizer'] = DashEventVisualizer(
                    event_bus=self.get_event_bus(),
                    figi=self._config.figi
                )
            except ImportError:
                self._logger.warning("Dash визуализатор недоступен")
                return None
        
        return self._instances['visualizer']
    
    def build_trading_system(self) -> Dict[str, Any]:
        """Собирает полную торговую систему"""
        return {
            'config': self._config,
            'event_bus': self.get_event_bus(),
            'session_controller': self.get_session_controller(),
            'dependencies': self.get_trading_dependencies(),
            'visualizer': self.get_visualizer()
        }
