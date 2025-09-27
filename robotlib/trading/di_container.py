"""
DI контейнер для торговой системы
"""
from typing import Optional, Dict, Any
from robotlib.utils.logger import get_logger
from robotlib.trading.trading_config import TradingConfig
from robotlib.trading.interfaces import TradingDependencies
from robotlib.trading.session_controller import SessionController
from robotlib.trading.session_stats import SessionStats
from robotlib.trading.portfolio_manager import PortfolioManager
from robotlib.trading.risk_manager import RiskManager, RiskLimits
from robotlib.trading.order_executor import OrderExecutor
from robotlib.trading.market_data_stream import MarketDataStream
from robotlib.trading.stream_config import StreamConfig
from robotlib.trading.candle_cache import CandleCache
from robotlib.trading.stream_watchdog import StreamWatchdog
from robotlib.trading.historical_data_loader import HistoricalDataLoader
from robotlib.trading.stream_registry import get_stream_registry
from robotlib.trading.position_sizing_service import PositionSizingService
from robotlib.trading.position_sizing_config import PositionSizingConfig
from robotlib.trading.position_manager import PositionManager
from robotlib.trading.position_manager_factory import PositionManagerFactory
from robotlib.strategies.long import LongStrategy
from robotlib.strategies.short import ShortStrategy
from robotlib.trading.api_client_factory import APIClientFactory
from robotlib.signal_manager import SignalManager
from robotlib.strategies.strategy_manager import StrategyManager
from robotlib.strategies.intent_arbiter import SimpleIntentArbiter
from robotlib.strategies.signal_dispatcher import VisualizationSignalDispatcher
from visualization.dash_event_visualizer import DashEventVisualizer
from robotlib.ingestion.order_execution_sink import OrderExecutionSink
from config_data.config import load_config
from visualization.adapters.sink_impl import TradingDataMapper, WsEventBroadcaster, TradingToUIBridge
from visualization.data_manager import VisualizationDataStore
from visualization.chart_builder import ChartBuilder
from visualization.ui_components import UIComponents
from visualization.channels.ws import WebSocketHub
from visualization.services.market_status_service import MarketStatusService
from robotlib.trading.position_restoration_service import PositionRestorationService

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
        # Создаем PositionSizingService с динамикой
        rm = await self.get_risk_manager()
        pm = await self.get_portfolio_manager()
        cfg = PositionSizingConfig(
            enable_dynamic_sizing=True,
            min_lots=1,
            max_lots=5,
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
        
        # Создаем стратегии с figi и PositionSizingService
        strategies = [
            LongStrategy(figi=self._config.figi, position_sizing_service=position_sizing_service),
            ShortStrategy(figi=self._config.figi, position_sizing_service=position_sizing_service)
        ]
        
        return strategies
    
    def get_data_manager(self) -> Optional[VisualizationDataStore]:
        """Получает data_manager (если визуализация включена)"""
        if not self._config.enable_visualization:
            return None
        return self._instances.get('data_manager')
    
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
            
            # Лимиты риска проверяются в SessionController при старте сессии
                
        return self._instances['risk_manager']
    
    
    async def get_order_executor(self) -> OrderExecutor:
        """Получает исполнитель ордеров"""
        if 'order_executor' not in self._instances:
            # Используем единый API клиент
            api_client = await self.get_api_client()
            # Создаём sink для сохранения ордеров (в ту же БД, что и свечи визуализатора при желании)
            order_sink: OrderExecutionSink | None = None
            order_sink = OrderExecutionSink(
                db_path="data/market.db",
                figi=self._config.figi,
            )
            self._logger.info("OrderExecutionSink для ордеров инициализирован")
            
            # Подключаем UI listener для ордеров
            # Проверяем, что визуализация включена, но не требуем обязательной инициализации data_manager
            # так как он может быть создан позже через get_visualizer
            
            listeners = []
            bridge = self._create_trading_bridge()
            if bridge is not None:
                listeners.append(bridge)
            self._instances['order_executor'] = OrderExecutor(
                api_client=api_client,
                order_sink=order_sink,
                listeners=listeners,
            )
        return self._instances['order_executor']
    
    def get_signal_manager(self) -> SignalManager:
        """Получает менеджер сигналов"""
        if 'signal_manager' not in self._instances:
            # SignalManager больше не нужен для визуализации - TradingToUIBridge обрабатывает сигналы
            self._instances['signal_manager'] = SignalManager(
                visualization_sink=None
            )
        return self._instances['signal_manager']
    
    async def get_strategy_manager(self) -> StrategyManager:
        """Получает менеджер стратегий"""
        if 'strategy_manager' not in self._instances:
            # Используем TradingToUIBridge для SignalDispatcher
            bridge = self._create_trading_bridge()
            if bridge is not None:
                dispatcher = VisualizationSignalDispatcher(bridge)
            else:
                from robotlib.strategies.signal_dispatcher import NullSignalDispatcher
                dispatcher = NullSignalDispatcher()
            
            strategies = await self._create_strategies()
            
            strategy_manager = StrategyManager(
                signal_manager=self.get_signal_manager(),
                risk_manager=await self.get_risk_manager(),
                portfolio_manager=await self.get_portfolio_manager(),
                order_executor=await self.get_order_executor(),
                strategies=strategies,
                signal_dispatcher=dispatcher,
                intent_arbiter=SimpleIntentArbiter(),
                position_manager=await self.get_position_manager(),
            )
            
            self._instances['strategy_manager'] = strategy_manager
        return self._instances['strategy_manager']    
    
    def get_trading_bridge(self) -> Optional[TradingToUIBridge]:
        """Получает TradingToUIBridge (если визуализация включена)"""
        return self._create_trading_bridge()
    
    def _create_trading_bridge(self) -> Optional[TradingToUIBridge]:
        """Создает TradingToUIBridge для связи торговой системы с UI"""
        if not self._config.enable_visualization:
            self._logger.debug("TradingToUIBridge не создан: визуализация отключена")
            return None
            
        # Проверяем, не создан ли уже bridge
        if 'trading_bridge' in self._instances:
            return self._instances['trading_bridge']
            
        visualizer = self.get_visualizer()
        dm = self.get_data_manager()
        
        if dm is None or visualizer is None:
            self._logger.warning(f"TradingToUIBridge не создан: visualizer={visualizer is not None}, dm={dm is not None}")
            return None
            
        try:
            data_mapper = TradingDataMapper(dm)
            ws = WsEventBroadcaster(visualizer._broadcast_ws)
            bridge = TradingToUIBridge(data_mapper, ws)
            
            # Устанавливаем callback для отправки снэпшотов по требованию
            visualizer.set_snapshot_callback(bridge.send_snapshot_on_demand)
            
            # Сохраняем bridge в инстансах для переиспользования
            self._instances['trading_bridge'] = bridge
            
            self._logger.info("TradingToUIBridge создан успешно и сохранен в инстансах")
            return bridge
        except Exception as e:
            self._logger.error(f"Ошибка создания TradingToUIBridge: {e}")
            return None
    
    async def get_market_data_stream(self) -> MarketDataStream:
        """Получает стрим рыночных данных с переиспользованием"""
        if 'market_data_stream' not in self._instances:
            # Проверяем реестр стримов
            registry = get_stream_registry()
            existing_stream = registry.get_stream(self._config.figi)
            
            if existing_stream:
                self._logger.info(f"Переиспользуем существующий стрим для {self._config.figi}")
                self._instances['market_data_stream'] = existing_stream
                return existing_stream
            
            # Создаем новый стрим
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

            # Создаем компоненты для MarketDataStream
            candle_cache = CandleCache(cache_size=100)
            historical_loader = HistoricalDataLoader(api_client, self._config.figi)
            watchdog = StreamWatchdog(
                stale_seconds=stream_cfg.watchdog_stale_seconds,
                require_open_market=stream_cfg.watchdog_require_open_market
            ) if stream_cfg.watchdog_enabled else None
            
            new_stream = MarketDataStream(
                api_client=api_client,
                figi=self._config.figi,
                candle_cache=candle_cache,
                historical_loader=historical_loader,
                watchdog=watchdog,
            )
            
            # Регистрируем стрим в реестре
            subscriber_id = f"trading_system_{id(self)}"
            registered_stream = registry.register_stream(
                self._config.figi, 
                new_stream, 
                subscriber_id
            )
            
            self._instances['market_data_stream'] = registered_stream
            
            # Создаем TradingToUIBridge как основной sink
            bridge = self._create_trading_bridge()
            if bridge is not None:
                self._instances['market_data_stream'].set_event_sink(bridge)
                self._logger.info("TradingToUIBridge установлен как event_sink для market_data_stream")
                # Периодические снэпшоты будут запущены в SessionController после загрузки начальных данных
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
            
            # Автозапуск потока данных (раньше это делал SessionInitializer)
            try:
                await self._instances['market_data_stream'].start()
                self._logger.info("✅ Поток рыночных данных запущен автоматически")
            except Exception as e:
                self._logger.warning(f"⚠️ Не удалось запустить поток данных: {e}")
                
        return self._instances['market_data_stream']
    
    async def get_position_manager(self) -> PositionManager:
        """Получает PositionManager БЕЗ автоматической синхронизации"""
        if 'position_manager' not in self._instances:
            risk_manager = await self.get_risk_manager()
            sync_service = await self.get_sync_service()
            self._instances['position_manager'] = await PositionManagerFactory.create_and_sync_position_manager(
                db_path=self._config.positions_db_path,
                risk_manager=risk_manager,
                sync_service=sync_service
            )
        return self._instances['position_manager']
    
    async def get_sync_service(self):
        """Получает сервис синхронизации позиций"""
        if 'sync_service' not in self._instances:
            from robotlib.trading.position_sync_service import PositionSyncService
            api_client = await self.get_api_client()
            restoration_service = PositionRestorationService(api_client, point_value=10.0)
            
            # Получаем UI bridge для уведомлений
            ui_bridge = None
            try:
                trading_deps = await self.get_trading_dependencies()
                ui_bridge = trading_deps.event_sink
            except Exception:
                pass  # UI bridge может быть недоступен
                
            self._instances['sync_service'] = PositionSyncService(
                self._config.positions_db_path, 
                api_client, 
                restoration_service,
                ui_bridge
            )
        return self._instances['sync_service']
    
    async def get_trading_dependencies(self) -> TradingDependencies:
        """Получает зависимости торговой системы"""
        if 'trading_dependencies' not in self._instances:
            self._instances['trading_dependencies'] = TradingDependencies(
                api_client=await self.get_api_client(),
                session_stats=self.get_session_stats(),
                portfolio_manager=await self.get_portfolio_manager(),
                risk_manager=await self.get_risk_manager(),
                order_executor=await self.get_order_executor(),
                market_data_stream=await self.get_market_data_stream(),
                signal_manager=self.get_signal_manager(),
                strategy_manager=await self.get_strategy_manager(),
                event_sink=self._create_trading_bridge(),
                position_manager=await self.get_position_manager(),
                data_manager=self.get_data_manager()
            )
        return self._instances['trading_dependencies']
    
    
    async def get_session_controller(self) -> SessionController:
        """Получает контроллер сессии"""
        if 'session_controller' not in self._instances:
            # Получаем зависимости (SessionInitializer больше не нужен)
            dependencies = await self.get_trading_dependencies()
            
            self._instances['session_controller'] = SessionController(
                config=self._config,
                dependencies=dependencies,
                force_start=True,
                visualizer=self.get_visualizer(host="127.0.0.1", port=8050, start_server=True)
            )
        return self._instances['session_controller']
    
    def get_visualizer(self, host: str = "127.0.0.1", port: int = 8050, start_server: bool = True) -> Optional[Any]:
        """Получает визуализатор (если включен)"""
        if not self._config.enable_visualization:
            return None
        
        if 'visualizer' not in self._instances:
            try:
                dm = VisualizationDataStore()
                self._instances['data_manager'] = dm
                cb = ChartBuilder()
                ui = UIComponents(self._config.figi, cb)
                ws_hub = WebSocketHub()
                ms_service = MarketStatusService()
                self._instances['visualizer'] = DashEventVisualizer(
                    figi=self._config.figi,
                    host=host,
                    port=port,
                    start_server=start_server,
                    chart_builder=cb,
                    ui_components=ui,
                    ws_hub=ws_hub,
                    market_status_service=ms_service,
                )
                # Мигрируем схему orders и подгружаем исторические данные для старта UI
                try:
                    dm.migrate_orders_schema(db_path="data/market.db")
                except Exception:
                    pass
                try:
                    dm.load_recent_candles(db_path="data/market.db", figi=self._config.figi, limit=300)
                except Exception:
                    pass
                try:
                    dm.load_recent_orders_today(db_path="data/market.db", figi=self._config.figi, limit=300)
                except Exception:
                    pass
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
