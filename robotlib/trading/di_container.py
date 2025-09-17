"""
DI контейнер для торговой системы
"""
from typing import Optional, Dict, Any
from typing import Callable, Dict, List
from robotlib.utils.logger import get_logger
from robotlib.trading.trading_config import TradingConfig
from robotlib.trading.interfaces import TradingDependencies
from robotlib.trading.session_controller import SessionController
from robotlib.trading.session_initializer import SessionInitializer
from robotlib.trading.session_stats import SessionStats
from robotlib.trading.portfolio_manager import PortfolioManager
from robotlib.trading.risk_manager import RiskManager, RiskLimits
from robotlib.trading.order_executor import OrderExecutor
from robotlib.trading.market_data_stream import MarketDataStream
from robotlib.trading.api_client_factory import APIClientFactory
from robotlib.signal_manager import SignalManager
from robotlib.strategies.strategy_manager import StrategyManager
from robotlib.strategies.signal_dispatcher import VisualizationSignalDispatcher
from visualization.dash_event_visualizer import DashEventVisualizer
from visualization.event_visualizer_interface import VisualizationSinkable
from robotlib.ingestion.db_sink import DBIngestionSink


class TradingSystemContainer:
    """DI контейнер для торговой системы"""
    
    def __init__(self, config: TradingConfig):
        self._config = config
        self._logger = get_logger(__name__)
        self._instances: Dict[str, Any] = {}
        
        # Валидация конфигурации
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Валидирует конфигурацию торговой системы"""
        if not self._config.figi:
            raise ValueError("FIGI не может быть пустым")
        
        if not hasattr(self._config, 'tcs_client') or not self._config.tcs_client:
            raise ValueError("TCS клиент не настроен")
        
        if not hasattr(self._config.tcs_client, 'token') or not self._config.tcs_client.token:
            raise ValueError("Токен TCS клиента не настроен")
        
        if not hasattr(self._config.tcs_client, 'account_id') or not self._config.tcs_client.account_id:
            raise ValueError("ID аккаунта TCS клиента не настроен")
        
        self._logger.info("✅ Конфигурация торговой системы валидна")
    
    
    def get_session_stats(self) -> SessionStats:
        """Получает статистику сессии"""
        if 'session_stats' not in self._instances:
            self._instances['session_stats'] = SessionStats()
        return self._instances['session_stats']
    
    async def get_api_client(self):
        """Получает инициализированный API клиент"""
        if 'api_client' not in self._instances:
            # Создаем и инициализируем API клиент через фабрику
            self._instances['api_client'] = await APIClientFactory.create_initialized_tinkoff_client(
                token=self._config.tcs_client.token,
                account_id=self._config.tcs_client.account_id,
                sandbox_token=self._config.tcs_client.sandbox_token
            )
        return self._instances['api_client']
    
    async def get_portfolio_manager(self) -> PortfolioManager:
        """Получает менеджер портфеля"""
        if 'portfolio_manager' not in self._instances:
            # Используем единый API клиент
            api_client = await self.get_api_client()
            
            self._instances['portfolio_manager'] = PortfolioManager(
                api_client=api_client,
                event_bus=None
            )
        return self._instances['portfolio_manager']
    
    async def get_risk_manager(self) -> RiskManager:
        """Получает менеджер рисков"""
        if 'risk_manager' not in self._instances:
            self._instances['risk_manager'] = RiskManager(
                portfolio_manager=await self.get_portfolio_manager(),
                risk_limits=RiskLimits(
                    max_daily_loss=50000.0,  # Дефолтное значение
                    max_position_size=100000.0  # Дефолтное значение
                )
            )
        return self._instances['risk_manager']
    
    async def get_order_executor(self) -> OrderExecutor:
        """Получает исполнитель ордеров"""
        if 'order_executor' not in self._instances:
            # Используем единый API клиент
            api_client = await self.get_api_client()
            # Создаём sink для сохранения ордеров (в ту же БД, что и свечи визуализатора при желании)
            order_sink: DBIngestionSink | None = None
            try:
                order_sink = DBIngestionSink(
                    db_path="data/market.db",
                    figi=self._config.figi,
                    batch_size=200,
                    flush_interval_sec=1.0,
                )
            except Exception:
                order_sink = None
            
            self._instances['order_executor'] = OrderExecutor(
                api_client=api_client,
                event_bus=None,
                order_sink=order_sink
            )
        return self._instances['order_executor']
    
    def get_signal_manager(self) -> SignalManager:
        """Получает менеджер сигналов"""
        if 'signal_manager' not in self._instances:
            visualizer = self.get_visualizer(host="127.0.0.1", port=8050, start_server=True)
            self._instances['signal_manager'] = SignalManager(
                event_bus=None,
                visualization_sink=visualizer if isinstance(visualizer, VisualizationSinkable) else None
            )
        return self._instances['signal_manager']
    
    async def get_strategy_manager(self) -> StrategyManager:
        """Получает менеджер стратегий"""
        if 'strategy_manager' not in self._instances:
            visualizer = self.get_visualizer(host="127.0.0.1", port=8050, start_server=True)
            dispatcher = VisualizationSignalDispatcher(visualizer) if visualizer else None
            strategy_manager = StrategyManager(
                signal_manager=self.get_signal_manager(),
                risk_manager=await self.get_risk_manager(),
                portfolio_manager=await self.get_portfolio_manager(),
                order_executor=await self.get_order_executor(),
                signal_dispatcher=dispatcher
            )
            
            # Стратегии добавляются автоматически в StrategyManager
            
            self._instances['strategy_manager'] = strategy_manager
        return self._instances['strategy_manager']
    
    async def get_market_data_stream(self) -> MarketDataStream:
        """Получает стрим рыночных данных"""
        if 'market_data_stream' not in self._instances:
            api_client = await self.get_api_client()
            
            self._instances['market_data_stream'] = MarketDataStream(
                api_client=api_client,
                figi=self._config.figi,
                cache_size=1000
            )
            # Инжектим sink в поток рыночных данных
            visualizer = self.get_visualizer(host="127.0.0.1", port=8050, start_server=True)
            if isinstance(visualizer, VisualizationSinkable):
                self._instances['market_data_stream'].set_visualization_sink(visualizer)
            # Подключаем стратегии к потоку свечей (генерация сигналов)
            try:
                strategy_manager = await self.get_strategy_manager()
                if not hasattr(self._instances['market_data_stream'], '_strategy_cb_registered'):
                    def _strategy_cb(candle):
                        try:
                            import asyncio as _asyncio
                            _asyncio.create_task(strategy_manager.on_candle(candle))
                        except Exception:
                            pass
                    self._instances['market_data_stream'].add_candle_callback(_strategy_cb)
                    setattr(self._instances['market_data_stream'], '_strategy_cb_registered', True)
            except Exception:
                # Если стратегий нет, продолжаем только с визуализатором
                pass
        return self._instances['market_data_stream']
    
    async def get_trading_dependencies(self) -> TradingDependencies:
        """Получает зависимости торговой системы"""
        if 'trading_dependencies' not in self._instances:
            # Используем единый API клиент
            api_client = await self.get_api_client()

            self._instances['trading_dependencies'] = TradingDependencies(
                api_client=api_client,
                session_stats=self.get_session_stats(),
                portfolio_manager=await self.get_portfolio_manager(),
                risk_manager=await self.get_risk_manager(),
                order_executor=await self.get_order_executor(),
                market_data_stream=await self.get_market_data_stream(),
                signal_manager=self.get_signal_manager(),
                strategy_manager=await self.get_strategy_manager()
            )
        return self._instances['trading_dependencies']
    
    async def get_session_initializer(self) -> SessionInitializer:
        """Получает инициализатор сессии"""
        if 'session_initializer' not in self._instances:
            # Получаем готовые TradingDependencies
            dependencies = await self.get_trading_dependencies()
            # Создаем SessionInitializer с готовыми dependencies
            self._instances['session_initializer'] = SessionInitializer(
                config=self._config,
                dependencies=dependencies
            )
        return self._instances['session_initializer']
    
    async def get_session_controller(self) -> SessionController:
        """Получает контроллер сессии"""
        if 'session_controller' not in self._instances:
            # Получаем зависимости и session_initializer отдельно
            dependencies = await self.get_trading_dependencies()
            session_initializer = await self.get_session_initializer()
            
            # Создаем TradingDependencies с session_initializer для SessionController
            controller_dependencies = TradingDependencies(
                api_client=dependencies.api_client,
                session_stats=dependencies.session_stats,
                portfolio_manager=dependencies.portfolio_manager,
                risk_manager=dependencies.risk_manager,
                order_executor=dependencies.order_executor,
                market_data_stream=dependencies.market_data_stream,
                signal_manager=dependencies.signal_manager,
                strategy_manager=dependencies.strategy_manager
            )
            # Добавляем session_initializer как атрибут
            controller_dependencies.session_initializer = session_initializer
            
            self._instances['session_controller'] = SessionController(
                config=self._config,
                dependencies=controller_dependencies,
                force_start=False,
                visualizer=self.get_visualizer(host="127.0.0.1", port=8050, start_server=True)
            )
        return self._instances['session_controller']
    
    def get_visualizer(self, host: str = "127.0.0.1", port: int = 8050, start_server: bool = True) -> Optional[Any]:
        """Получает визуализатор (если включен)"""
        if not self._config.enable_visualization:
            return None
        
        if 'visualizer' not in self._instances:
            try:
                self._instances['visualizer'] = DashEventVisualizer(
                    event_bus=None,
                    figi=self._config.figi,
                    host=host,
                    port=port,
                    start_server=start_server
                )
            except ImportError:
                self._logger.warning("Dash визуализатор недоступен")
                return None
        
        return self._instances['visualizer']
    
    async def build_trading_system(self, host: str = "127.0.0.1", port: int = 8050, start_server: bool = True) -> Dict[str, Any]:
        """Собирает полную торговой системы"""
        return {
            'config': self._config,
            'session_controller': await self.get_session_controller(),
            'dependencies': await self.get_trading_dependencies(),
            'visualizer': self.get_visualizer(host=host, port=port, start_server=start_server)
        }
