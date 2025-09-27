"""
Интерфейсы для торговых компонентов - обеспечивают инверсию зависимостей
"""
from typing import Protocol, Optional, List, Dict, Any, runtime_checkable
from visualization.interfaces import VisualizationDataStoreable

from robotlib.signal_types import Signal
from robotlib.trading.order_types import OrderIntent, OrderExecution, OrderDirection
from robotlib.trading.order_executor import OrderResult
from robotlib.trading.portfolio_manager import Portfolio, Position
from robotlib.trading.session_interfaces import SessionStatsable
from robotlib.trading.risk_manager import RiskLimits, RiskCheck
from tinkoff.invest import Candle, HistoricCandle
from robotlib.trading_interfaces import TradingEventSinkable


@runtime_checkable
class PositionManageable(Protocol):
    """Интерфейс для PositionManager - управление позициями и FIFO логикой"""
    
    def get_position(self, figi: str) -> Optional[Position]:
        """Получение позиции из кэша"""
        pass
    
    async def get_current_fifo_queue(self, figi: str) -> List[Any]:
        """Получение текущей FIFO очереди для позиции"""
        pass
    
    async def get_loss_positions(
        self, 
        figi: str, 
        current_price: float, 
        loss_threshold: float
    ) -> List[Any]:
        """Получение убыточных позиций по FIFO"""
        pass
    
    async def get_profit_positions(
        self, 
        figi: str, 
        current_price: float
    ) -> List[Any]:
        """Получение прибыльных позиций по FIFO"""
        pass
    
    async def add_to_fifo(
        self, 
        figi: str, 
        quantity: int, 
        price: float, 
        order_id: str,
        direction: OrderDirection
    ):
        """Добавление позиции в FIFO очередь"""
        pass
    
    async def remove_from_fifo(
        self, 
        figi: str, 
        quantity: int
    ):
        """Удаление позиций из FIFO очереди по принципу FIFO"""
        pass
    
    async def update_position_after_trade(
        self, 
        figi: str, 
        quantity_delta: int, 
        price: float
    ):
        """Обновление позиции после сделки"""
        pass
    
    async def sync_on_startup(self, max_retries: int = 3) -> Dict[str, Position]:
        """Синхронизация позиций при старте системы"""
        pass


class APIClientable(Protocol):
    """Интерфейс для API клиента"""
    
    async def __aenter__(self):
        """Асинхронный вход в контекст"""
        pass
    
    async def __aexit__(
        self, 
        exc_type, 
        exc_val, 
        exc_tb
    ):
        """Асинхронный выход из контекста"""
        pass


@runtime_checkable
class TinkoffAPIClientable(Protocol):
    """Интерфейс для TinkoffAPIClient - полный набор методов для торговли"""
    
    async def __aenter__(self):
        """Асинхронный вход в контекст"""
        pass
    
    async def __aexit__(
        self, 
        exc_type, 
        exc_val, 
        exc_tb
    ):
        """Асинхронный выход из контекста"""
        pass
    
    async def check_market_availability(self) -> bool:
        """Проверяет доступность рынка"""
        pass
    
    async def place_order(
        self,
        figi: str,
        quantity: int,
        price: Optional[float] = None,
        direction: str = "buy",
        order_type: str = "market",
        order_id: Optional[str] = None
    ) -> OrderResult:
        """Размещает ордер"""
        pass
    
    async def get_order_status(self, order_id: str) -> Optional[Any]:
        """Получает статус ордера"""
        pass
    
    async def wait_for_order_execution(
        self, 
        order_id: str, 
        timeout: int = 30, 
        check_interval: float = 1.0
    ) -> OrderResult:
        """Ожидает исполнения ордера"""
        pass
    
    async def cancel_order(self, order_id: str) -> bool:
        """Отменяет ордер"""
        pass
    
    async def buy_market(self, figi: str, quantity: int, wait_execution: bool = True) -> OrderResult:
        """Покупка по рыночной цене"""
        pass
    
    async def sell_market(self, figi: str, quantity: int, wait_execution: bool = True) -> OrderResult:
        """Продажа по рыночной цене"""
        pass
    
    async def buy_limit(self, figi: str, quantity: int, price: float) -> OrderResult:
        """Покупка по лимитной цене"""
        pass
    
    async def sell_limit(self, figi: str, quantity: int, price: float) -> OrderResult:
        """Продажа по лимитной цене"""
        pass
    
    async def get_portfolio(self) -> Any:
        """Получает портфель"""
        pass
    
    async def get_positions(self) -> Any:
        """Получает позиции"""
        pass
    
    async def get_operations_history(self, from_date, to_date) -> Any:
        """Получает историю операций"""
        pass
    
    async def get_instrument_by_figi(self, figi: str) -> Any:
        """Получает информацию об инструменте по FIGI"""
        pass
    
    async def get_candles(self, figi: str, from_date, to_date, interval) -> Any:
        """Получает свечи"""
        pass
    
    async def create_market_data_stream(self) -> Any:
        """Создает стрим рыночных данных"""
        pass
    
    async def get_futures_margin(self, figi: str) -> Optional[dict]:
        """Получает информацию о гарантийном обеспечении для фьючерса"""
        pass
    
    async def get_accounts(self) -> Any:
        """Получает список аккаунтов"""
        pass
    
    async def get_user_info(self) -> Any:
        """Получает информацию о пользователе"""
        pass
    
    def is_sandbox(self) -> bool:
        """Проверяет, используется ли песочница"""
        pass


class OrderExecutable(Protocol):
    """Интерфейс для исполнителя ордеров"""
    
    async def execute_order(self, order_intent: OrderIntent) -> OrderExecution:
        """Выполняет OrderIntent и возвращает OrderExecution"""
        pass
    
    async def buy_market(self, figi: str, quantity: int, wait_execution: bool = True) -> OrderResult:
        """Покупка по рыночной цене (старый метод для обратной совместимости)"""
        pass
    
    async def sell_market(self, figi: str, quantity: int, wait_execution: bool = True) -> OrderResult:
        """Продажа по рыночной цене (старый метод для обратной совместимости)"""
        pass
    
    async def buy_limit(self, figi: str, quantity: int, price: float) -> OrderResult:
        """Покупка по лимитной цене (старый метод для обратной совместимости)"""
        pass
    
    async def sell_limit(self, figi: str, quantity: int, price: float) -> OrderResult:
        """Продажа по лимитной цене (старый метод для обратной совместимости)"""
        pass


class SignalManageable(Protocol):
    """Интерфейс для менеджера сигналов"""
    
    def add_candle(self, candle: Candle | HistoricCandle) -> Optional[Signal]:
        """Добавляет свечу и возвращает сигнал если есть"""
        pass
    
    @property
    def candles(self) -> List[Dict[str, Any]]:
        """Возвращает список свечей"""
        pass


class StrategyManageable(Protocol):
    """Интерфейс для менеджера стратегий"""
    
    async def initialize(self, figi: str, point_value: float = None, contracts_per_lot: int = None) -> None:
        """Инициализирует стратегии"""
        pass
    
    async def on_candle(self, candle) -> None:
        """Обрабатывает свечу через стратегии"""
        pass
    
    async def close_all_positions(self) -> None:
        """Закрывает все позиции во всех стратегиях"""
        pass


class MarketDataStreamable(Protocol):
    """Интерфейс для потока рыночных данных"""
    
    def add_signal_callback(self, callback) -> None:
        """Добавляет колбэк для обработки сигналов"""
        pass
    
    async def start(self) -> None:
        """Запускает поток данных"""
        pass
    
    async def stop(self) -> None:
        """Останавливает поток данных"""
        pass
    
    async def get_latest_candles(self, count: int = 10) -> List[Candle]:
        """Возвращает последние N свечей"""
        pass
    
    async def get_current_price(self) -> Optional[float]:
        """Возвращает текущую цену"""
        pass
    
    def get_cached_candles(self) -> List[Candle]:
        """Возвращает все кэшированные свечи"""
        pass
    
    def get_cache_size(self) -> int:
        """Возвращает размер кэша"""
        pass
    
    def clear_cache(self) -> None:
        """Очищает кэш свечей"""
        pass


class PortfolioManageable(Protocol):
    """Интерфейс для менеджера портфеля"""
    
    async def get_portfolio(self) -> Portfolio:
        """Получает портфель"""
        pass
    
    async def get_deposit(self) -> float:
        """Получает депозит"""
        pass
    
    async def get_guarantee_deposit(self, figi: str) -> float:
        """Получает гарантийное обеспечение"""
        pass
    
    async def get_position(self, figi: str) -> Optional[Position]:
        """Получает позицию по инструменту"""
        pass
    
    async def close_position(self, figi: str) -> bool:
        """Закрывает позицию"""
        pass


class RiskManageable(Protocol):
    """Интерфейс для менеджера рисков"""
    
    @property
    def risk_limits(self) -> RiskLimits:
        """Возвращает лимиты рисков"""
        pass
    
    async def check_trade_risk(self, figi: str, quantity: int, direction: str) -> RiskCheck:
        """Проверяет риск сделки"""
        pass
    
    async def check_stop_loss(self, figi: str) -> Optional[RiskCheck]:
        """Проверяет стоп-лосс"""
        pass


class TradingDependencies:
    """Контейнер для всех зависимостей торговой системы"""
    
    def __init__(
        self,
        api_client: APIClientable,
        order_executor: OrderExecutable,
        portfolio_manager: PortfolioManageable,
        risk_manager: RiskManageable,
        signal_manager: SignalManageable,
        strategy_manager: StrategyManageable,
        market_data_stream: MarketDataStreamable,
        session_stats: SessionStatsable,
        event_sink: TradingEventSinkable,
        position_manager: PositionManageable,  # PositionManager (обязательный)
        data_manager: VisualizationDataStoreable | None = None
    ):
        self.api_client = api_client
        self.order_executor = order_executor
        self.portfolio_manager = portfolio_manager
        self.risk_manager = risk_manager
        self.signal_manager = signal_manager
        self.strategy_manager = strategy_manager
        self.market_data_stream = market_data_stream
        self.session_stats = session_stats
        self.event_sink = event_sink
        self.position_manager = position_manager
        self.data_manager = data_manager
