#!/usr/bin/env python3
"""
Фабрика для создания TradingSignalsVisualizer
"""
from typing import Any, Optional
from robotlib.utils.logger import get_logger
from robotlib.trading.trading_config import TradingConfig as TradingSessionConfig
from robotlib.trading.risk_manager import RiskLimits
from robotlib.trading.trading_session import TradingSession
from .trading_dependencies_factory import TradingDependenciesFactory
from ..trading_visualizer import TradingSignalsVisualizer
from ..data_manager import DataManager
from ..chart_builder import ChartBuilder
from ..ui_components import UIComponents
from ..trading_session_manager import TradingSessionManager
from ..factories import VisualizerParams
from config_data.config import load_config


class TradingSignalsVisualizerFactory:
    """Фабрика для создания TradingSignalsVisualizer с правильной инжекцией зависимостей"""
    
    def __init__(self, service_locator=None):
        self.service_locator = service_locator
        self.logger = get_logger(__name__)
    
    def create_visualizer(self, params: VisualizerParams) -> TradingSignalsVisualizer:
        """Создает TradingSignalsVisualizer с правильной DI"""
        try:
            # Создаем модули
            data_manager = DataManager()
            chart_builder = ChartBuilder()
            ui_components = UIComponents(params.figi)
            
            # Создаем TradingSessionManager если нужно
            trading_session_manager = None
            if params.with_trading_session and self.service_locator:
                # Создаем TradingSession с правильной DI
                
                # Создаем конфигурацию
                trading_config = TradingSessionConfig(
                    figi=params.figi,
                    deposit=None,
                    signal_manager_params=params.strategy_params or {},
                    risk_limits=RiskLimits(
                        max_daily_loss=50000,
                        max_position_size=50000,
                        percent_from_deposit=50.0,
                        items_per_trade=20,
                        stop_loss_threshold=3.0
                    ),
                    auto_close_positions=False
                )
                
                # Создаем зависимости
                dependencies_factory = TradingDependenciesFactory()
                try:
                    config = load_config()
                    dependencies = dependencies_factory.create_real_dependencies(config)
                except Exception as e:
                    self.logger.warning(f"Не удалось создать реальные зависимости: {e}")
                    dependencies = dependencies_factory.create_mock_dependencies()
                
                # Создаем TradingSession
                trading_session = TradingSession(
                    config=trading_config,
                    dependencies=dependencies
                )
                
                # Создаем TradingSessionManager с готовыми зависимостями
                trading_session_manager = TradingSessionManager(
                    trading_session=trading_session,
                    strategy_params=params.strategy_params or {}
                )
            
            return TradingSignalsVisualizer(
                data_manager=data_manager,
                chart_builder=chart_builder,
                ui_components=ui_components,
                trading_session_manager=trading_session_manager,
                figi=params.figi,
                update_interval=params.update_interval
            )
        except Exception as e:
            self.logger.error(f"Ошибка создания TradingSignalsVisualizer: {e}")
            raise
