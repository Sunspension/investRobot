"""
Фабрика для создания визуализатора торговой системы
"""
from typing import Optional
from robotlib.utils.logger import get_logger
from robotlib.trading.visualizer_interface import TradingVisualizerable, MockTradingVisualizer
from robotlib.trading.trading_config import TradingConfig


class TradingVisualizerFactory:
    """Фабрика для создания визуализатора торговой системы"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def create_visualizer(
        self, 
        config: TradingConfig,
        host: str = "127.0.0.1",
        port: int = 8050
    ) -> Optional[TradingVisualizerable]:
        """
        Создает визуализатор на основе конфигурации
        
        Args:
            config: Конфигурация торговой системы
            host: Хост для веб-интерфейса
            port: Порт для веб-интерфейса
            
        Returns:
            Визуализатор или None, если визуализация отключена
        """
        if not config.enable_visualization:
            self.logger.info("Визуализация отключена в конфигурации")
            return None
        
        try:
            # Импортируем компоненты только при необходимости
            from visualization.trading_visualizer_adapter import TradingVisualizerAdapter
            from visualization.data_manager import DataManager
            from visualization.chart_builder import ChartBuilder
            from visualization.ui_components import UIComponents
            from visualization.interfaces import MockStrategyDataProvider
            
            # Создаем зависимости
            data_manager = DataManager()
            chart_builder = ChartBuilder()
            ui_components = UIComponents(config.figi)
            strategy_data_provider = MockStrategyDataProvider()  # Пока используем мок
            
            visualizer = TradingVisualizerAdapter(
                data_manager=data_manager,
                chart_builder=chart_builder,
                ui_components=ui_components,
                strategy_data_provider=strategy_data_provider,
                figi=config.figi,
                host=host,
                port=port
            )
            
            self.logger.info(f"Создан визуализатор для инструмента {config.figi}")
            return visualizer
            
        except ImportError as e:
            self.logger.error(f"Не удалось импортировать визуализатор: {e}")
            self.logger.info("Создаем мок визуализатор")
            return MockTradingVisualizer()
        
        except Exception as e:
            self.logger.error(f"Ошибка создания визуализатора: {e}")
            self.logger.info("Создаем мок визуализатор")
            return MockTradingVisualizer()
    
    def create_mock_visualizer(self) -> TradingVisualizerable:
        """
        Создает мок визуализатор для тестирования
        
        Returns:
            Мок визуализатор
        """
        self.logger.info("Создан мок визуализатор")
        return MockTradingVisualizer()
