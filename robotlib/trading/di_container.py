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
from robotlib.trading.stream_config import StreamConfig
from robotlib.trading.position_sizing_service import PositionSizingService
from robotlib.trading.position_sizing_config import PositionSizingConfig
from robotlib.strategies.long import LongStrategy
from robotlib.strategies.short import ShortStrategy
from robotlib.trading.api_client_factory import APIClientFactory
from robotlib.signal_manager import SignalManager
from robotlib.strategies.strategy_manager import StrategyManager
from robotlib.strategies.signal_dispatcher import VisualizationSignalDispatcher
from visualization.dash_event_visualizer import DashEventVisualizer
from robotlib.visualization_interfaces import TradingEventSinkable
from robotlib.ingestion.db_sink import DBIngestionSink
from config_data.config import load_config

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
    
    async def _create_strategies(self):
        """Создает стратегии с их зависимостями"""
        # Создаем PositionSizingService с динамикой, масштаб — от RiskManager
        rm = await self.get_risk_manager()
        pm = await self.get_portfolio_manager()
        cfg = PositionSizingConfig(
            enable_dynamic_sizing=True,
            min_lots=1,
            max_lots=100,
        )
        try:
            cfg.system_state_scale = await rm.get_system_state_scale()
            cfg.active_orders_go_estimate = rm.get_active_orders_go_estimate()
        except Exception:
            pass
        position_sizing_service = PositionSizingService(
            risk_manager=rm,
            portfolio_manager=pm,
            config=cfg,
        )
        
        # Создаем стратегии
        strategies = [
            LongStrategy(
                risk_manager=await self.get_risk_manager(),
                portfolio_manager=await self.get_portfolio_manager(),
                position_sizing_service=position_sizing_service
            ),
            ShortStrategy(
                risk_manager=await self.get_risk_manager(),
                portfolio_manager=await self.get_portfolio_manager(),
                position_sizing_service=position_sizing_service
            )
        ]
        
        return strategies
    
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
                api_client=api_client
            )
        return self._instances['portfolio_manager']
    
    async def get_risk_manager(self) -> RiskManager:
        """Получает менеджер рисков"""
        if 'risk_manager' not in self._instances:
            self._instances['risk_manager'] = RiskManager(
                portfolio_manager=await self.get_portfolio_manager(),
                risk_limits=RiskLimits(
                    max_daily_loss=50000.0,
                    trading_enabled=True,
                    max_position_go=None,
                    max_open_positions=None,
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
                self._logger.info("DBIngestionSink для ордеров инициализирован")
            except Exception as e:
                self._logger.warning(f"DBIngestionSink недоступен, ордера не будут писаться: {e}")
                order_sink = None
            
            # Подключаем UI listener для ордеров
            viz = self.get_visualizer()
            dm = getattr(viz, "_data_manager", None)
            if self._config.enable_visualization and dm is None:
                raise RuntimeError("DataManager не инициализирован при включенной визуализации")
            from visualization.adapters.sink_impl import DataManagerSink, WsEventBroadcaster, TradingToUIBridge
            listeners = []
            if dm is not None:
                data_sink = DataManagerSink(dm)
                ws = WsEventBroadcaster(viz._broadcast_ws)
                listeners.append(TradingToUIBridge(data_sink, ws))
            self._instances['order_executor'] = OrderExecutor(
                api_client=api_client,
                order_sink=order_sink,
                listeners=listeners,
            )
        return self._instances['order_executor']
    
    def get_signal_manager(self) -> SignalManager:
        """Получает менеджер сигналов"""
        if 'signal_manager' not in self._instances:
            visualizer = self.get_visualizer(host="127.0.0.1", port=8050, start_server=True)
            self._instances['signal_manager'] = SignalManager(
                visualization_sink=visualizer if isinstance(visualizer, TradingEventSinkable) else None
            )
        return self._instances['signal_manager']
    
    async def get_strategy_manager(self) -> StrategyManager:
        """Получает менеджер стратегий"""
        if 'strategy_manager' not in self._instances:
            visualizer = self.get_visualizer(host="127.0.0.1", port=8050, start_server=True)
            dispatcher = VisualizationSignalDispatcher(visualizer) if visualizer else None
            strategies = await self._create_strategies()
            
            strategy_manager = StrategyManager(
                signal_manager=self.get_signal_manager(),
                risk_manager=await self.get_risk_manager(),
                portfolio_manager=await self.get_portfolio_manager(),
                order_executor=await self.get_order_executor(),
                strategies=strategies,
                signal_dispatcher=dispatcher
            )
            
            self._instances['strategy_manager'] = strategy_manager
        return self._instances['strategy_manager']
    
    async def get_market_data_stream(self) -> MarketDataStream:
        """Получает стрим рыночных данных"""
        if 'market_data_stream' not in self._instances:
            api_client = await self.get_api_client()
            
            # Собираем StreamConfig. Если у TradingConfig в будущем появится ссылка,
            # можно будет передавать её напрямую. Пока формируем из глобального .env
            # либо используем дефолты (явно, через отдельный конфиг).
            try:
                env_cfg = load_config()
                stream_cfg = StreamConfig(
                    watchdog_enabled=getattr(env_cfg, 'watchdog_enabled', True),
                    watchdog_stale_seconds=getattr(env_cfg, 'watchdog_stale_seconds', 120),
                    watchdog_require_open_market=getattr(env_cfg, 'watchdog_require_open_market', True),
                )
            except Exception:
                stream_cfg = StreamConfig()

            self._instances['market_data_stream'] = MarketDataStream(
                api_client=api_client,
                figi=self._config.figi,
                cache_size=100,
                watchdog_enabled=stream_cfg.watchdog_enabled,
                watchdog_stale_seconds=stream_cfg.watchdog_stale_seconds,
                watchdog_require_open_market=stream_cfg.watchdog_require_open_market,
            )
            # Инжектим sink в поток рыночных данных
            visualizer = self.get_visualizer(host="127.0.0.1", port=8050, start_server=True)
            if isinstance(visualizer, TradingEventSinkable):
                self._instances['market_data_stream'].set_event_sink(visualizer)
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

            # Визуализатор и его DataManager (если включен)
            viz = self.get_visualizer(host="127.0.0.1", port=8050, start_server=True)
            # Требуем DataManager, если визуализация включена
            dm = getattr(viz, "_data_manager", None)
            if dm is None and self._config.enable_visualization:
                raise RuntimeError("DataManager не инициализирован при включенной визуализации")
            self._instances['trading_dependencies'] = TradingDependencies(
                api_client=api_client,
                session_stats=self.get_session_stats(),
                portfolio_manager=await self.get_portfolio_manager(),
                risk_manager=await self.get_risk_manager(),
                order_executor=await self.get_order_executor(),
                market_data_stream=await self.get_market_data_stream(),
                signal_manager=self.get_signal_manager(),
                strategy_manager=await self.get_strategy_manager(),
                data_manager=dm,
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
                strategy_manager=dependencies.strategy_manager,
                data_manager=dependencies.data_manager,
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
                from visualization.data_manager import DataManager
                from visualization.chart_builder import ChartBuilder
                from visualization.ui_components import UIComponents
                from visualization.channels.ws import WebSocketHub
                from visualization.services.market_status_service import MarketStatusService
                dm = DataManager()
                cb = ChartBuilder()
                ui = UIComponents(self._config.figi, cb)
                ws_hub = WebSocketHub()
                ms_service = MarketStatusService()
                self._instances['visualizer'] = DashEventVisualizer(
                    figi=self._config.figi,
                    host=host,
                    port=port,
                    start_server=start_server,
                    data_manager=dm,
                    chart_builder=cb,
                    ui_components=ui,
                    ws_hub=ws_hub,
                    market_status_service=ms_service,
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
