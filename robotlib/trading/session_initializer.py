"""
Класс для инициализации компонентов торговой сессии
"""
from typing import Optional
from robotlib.trading.interfaces import TradingDependencies
from robotlib.trading.session_interfaces import SessionInitializable
from robotlib.trading.trading_config import TradingConfig
from robotlib.utils.logger import get_logger


class SessionInitializer(SessionInitializable):
    """Класс для инициализации компонентов торговой сессии"""
    
    def __init__(self, config: TradingConfig, dependencies: TradingDependencies):
        self.config = config
        self.dependencies = dependencies
        self.logger = get_logger(__name__)
    
    async def initialize_components(self) -> None:
        """Инициализирует все компоненты системы"""
        self.logger.info("Инициализация компонентов торговой сессии...")
        
        # Инициализация стратегий
        await self._initialize_strategies()
        
        # Инициализация потоков данных
        await self._initialize_data_streams()
        
        # Проверка лимитов риска
        await self._check_risk_limits()
        
        self.logger.info("Компоненты успешно инициализированы")
    
    async def initialize_strategies(self) -> None:
        """Инициализирует стратегии"""
        await self._initialize_strategies()
    
    async def initialize_data_streams(self) -> None:
        """Инициализирует потоки данных"""
        await self._initialize_data_streams()
    
    async def check_risk_limits(self) -> None:
        """Проверяет лимиты риска"""
        await self._check_risk_limits()
    
    async def _initialize_strategies(self) -> None:
        """Инициализирует стратегии"""
        self.logger.info("Инициализация стратегий...")
        
        # Получаем параметры для стратегий
        point_value = await self._get_point_value()
        contracts_per_lot = await self._get_contracts_per_lot()
        
        # Инициализируем стратегии
        await self.dependencies.strategy_manager.initialize(
            figi=self.config.figi,
            point_value=point_value,
            contracts_per_lot=contracts_per_lot
        )
        
        self.logger.info("Стратегии инициализированы")
    
    async def _initialize_data_streams(self) -> None:
        """Инициализирует потоки данных"""
        self.logger.info("Инициализация потоков данных...")
        
        # Инициализируем поток рыночных данных
        if hasattr(self.dependencies, 'market_data_stream') and self.dependencies.market_data_stream:
            await self.dependencies.market_data_stream.start()
            self.logger.info("Поток рыночных данных запущен")
    
    async def _check_risk_limits(self) -> None:
        """Проверяет лимиты риска"""
        self.logger.debug("Проверка лимитов риска...")
        
        # Получаем текущий баланс
        portfolio = await self.dependencies.portfolio_manager.get_portfolio()
        current_balance = portfolio.total_amount
        
        # Проверяем лимиты только если есть средства
        if current_balance > 0:
            risk_check = await self.dependencies.risk_manager.check_trade_risk(
                figi=self.config.figi,
                quantity=1,  # Минимальное количество для проверки
                price=100.0,  # Фиктивная цена
                direction="buy"
            )
            
            if not risk_check.passed:
                self.logger.debug(f"Предупреждение по лимитам риска: {risk_check.message}")
            else:
                self.logger.debug("Лимиты риска в порядке")
        else:
            self.logger.debug("Портфель пуст, пропускаем проверку лимитов")
    
    async def _get_point_value(self) -> Optional[float]:
        """Получает стоимость пункта для инструмента"""
        try:
            # Пытаемся получить из API
            if hasattr(self.dependencies, 'api_client') and self.dependencies.api_client:
                margin_info = await self.dependencies.api_client.get_futures_margin(self.config.figi)
                if margin_info and hasattr(margin_info, 'min_price_increment'):
                    return float(margin_info.min_price_increment.units)
        except Exception as e:
            self.logger.warning(f"Не удалось получить стоимость пункта из API: {e}")
        
        # Возвращаем значение по умолчанию для фьючерса на MOEX
        return 1.0
    
    async def _get_contracts_per_lot(self) -> Optional[int]:
        """Получает количество контрактов в лоте"""
        try:
            # Пытаемся получить из API
            if hasattr(self.dependencies, 'api_client') and self.dependencies.api_client:
                margin_info = await self.dependencies.api_client.get_futures_margin(self.config.figi)
                if margin_info and hasattr(margin_info, 'lot'):
                    return margin_info.lot
        except Exception as e:
            self.logger.warning(f"Не удалось получить размер лота из API: {e}")
        
        # Возвращаем значение по умолчанию для фьючерса на MOEX
        return 1
