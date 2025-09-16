import pandas as pd
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import asdict
from pandas import DataFrame

from robotlib.signal_manager import SignalManager
from robotlib.signal_types import Signal, Order
from robotlib.trading.order_types import OrderIntent, OrderExecution
from robotlib.strategies.strategy_interface import Strategyable
from robotlib.strategies.long import LongStrategy
from robotlib.strategies.short import ShortStrategy
from robotlib.trading.interfaces import StrategyManageable, OrderExecutable
from robotlib.strategies.signal_dispatcher import SignalDispatchable, VisualizationSignalDispatcher
from robotlib.utils.logger import get_logger
from tinkoff.invest import Candle, HistoricCandle

class StrategyManager(StrategyManageable):
    """
    Менеджер, собирающий свечи в SignalManager,
    и запускающий произвольное количество стратегий,
    комбинирующий торговые решения.
    """

    @property
    def candles(self) -> DataFrame:
        return pd.DataFrame(self._signal_manager.candles)
    
    @property
    def trades(self) -> DataFrame:
        return pd.DataFrame([asdict(order) for order in self._orders])
    
    @property
    def income(self) -> float:
        return sum(strategy.income for strategy in self._strategies)
    
    def get_macd_data(self) -> List[dict]:
        """Возвращает данные MACD для анализа сигналов"""
        try:
            macd_data = []
            for macd_point in self._signal_manager._macd:
                macd_data.append({
                    'macd': macd_point.macd,
                    'signal': macd_point.signal,
                    'histogram': macd_point.histogram
                })
            return macd_data
        except AttributeError:
            return []
    
    def has_strategies(self) -> bool:
        """Проверяет, инициализированы ли стратегии"""
        return len(self._strategies) > 0
    
    def get_strategies_count(self) -> int:
        """Возвращает количество стратегий"""
        return len(self._strategies)
    
    def get_strategies(self) -> List[Strategyable]:
        """Возвращает список стратегий"""
        return self._strategies.copy()
    
    @property
    def signal_manager(self) -> SignalManager:
        """Возвращает SignalManager"""
        return self._signal_manager

    
    def __init__(
        self, 
        signal_manager: SignalManager, 
        risk_manager,
        portfolio_manager,
        order_executor: OrderExecutable = None,
        strategies: List[Strategyable] = None,
        signal_dispatcher: Optional[SignalDispatchable] = None,
    ):
        self._signal_manager = signal_manager
        self._risk_manager = risk_manager
        self._portfolio_manager = portfolio_manager
        self._order_executor = order_executor
        self._signal_dispatcher = signal_dispatcher
        self._orders = []
        self.logger = get_logger(__name__)
        
        # Если стратегии не переданы, создаем стандартные
        if strategies is None:
            self._strategies = [
                LongStrategy(risk_manager=risk_manager, portfolio_manager=portfolio_manager),
                ShortStrategy(risk_manager=risk_manager, portfolio_manager=portfolio_manager)
            ]
        else:
            self._strategies = strategies
        
        # Инициализация стратегий завершена

    async def initialize(self, figi: str = "FUTIMOEXF000", point_value: float = None, contracts_per_lot: int = None) -> None:
        """
        Инициализирует все стратегии при старте торговли
        
        Args:
            figi: FIGI инструмента для торговли
            point_value: Стоимость одного пункта (получена из API)
            contracts_per_lot: Количество контрактов в лоте (получено из API)
        """
        for strategy in self._strategies:
            if hasattr(strategy, 'initialize'):
                await strategy.initialize(figi, point_value, contracts_per_lot)

    async def on_candle(self, candle: Candle | HistoricCandle):
        
        
        signal: Signal = self._signal_manager.add_candle(candle)
        if not signal:
            return
        # Отправляем сигнал в диспетчер, если есть
        if self._signal_dispatcher is not None:
            try:
                price = float(getattr(candle.close, 'units', 0) + getattr(candle.close, 'nano', 0) / 1e9)
            except Exception:
                price = 0.0
            await self._signal_dispatcher.dispatch_signal(signal, getattr(candle, 'figi', 'unknown'), price)

        # Выполняем все стратегии
        for strategy in self._strategies:
            order_intents: list[OrderIntent] = await strategy.execute(signal)
            
            # Если есть OrderExecutor, выполняем ордера и передаем результаты в стратегии
            if self._order_executor:
                for order_intent in order_intents:
                    try:
                        # Выполняем ордер
                        execution = await self._order_executor.execute_order(order_intent)
                        
                        # Передаем результат исполнения в стратегию
                        if hasattr(strategy, '_process_execution'):
                            strategy._process_execution(execution)
                        
                        self.logger.info(f"Ордер выполнен: {execution}")
                        
                    except Exception as e:
                        self.logger.error(f"Ошибка выполнения ордера {order_intent}: {e}")
            else:
                # Если нет OrderExecutor, просто сохраняем намерения
                self._orders.extend(order_intents)
    
    def close_position(self, candle: Candle | HistoricCandle):
        # Закрываем позиции во всех стратегиях
        for strategy in self._strategies:
            order_intent = strategy.close_position(candle)
            if order_intent:
                self._orders.append(order_intent)
    
    async def close_all_positions(self) -> None:
        """Закрывает все позиции во всех стратегиях"""
        self.logger.info("Закрытие всех позиций через стратегии...")
        
        for strategy in self._strategies:
            try:
                # Закрываем позиции в каждой стратегии
                order_intent = strategy.close_position(None)  # None означает закрыть все позиции
                if order_intent:
                    # Если есть OrderExecutor, выполняем ордер и передаем результат в стратегию
                    if self._order_executor:
                        try:
                            execution = await self._order_executor.execute_order(order_intent)
                            
                            # Передаем результат исполнения в стратегию
                            if hasattr(strategy, '_process_execution'):
                                strategy._process_execution(execution)
                            
                            self.logger.info(f"Позиция закрыта в стратегии {strategy.__class__.__name__}: {execution}")
                            
                        except Exception as e:
                            self.logger.error(f"Ошибка выполнения ордера закрытия позиции: {e}")
                    else:
                        # Если нет OrderExecutor, просто сохраняем намерение
                        self._orders.append(order_intent)
                        self.logger.info(f"Закрыта позиция в стратегии {strategy.__class__.__name__}")
                        
            except Exception as e:
                self.logger.error(f"Ошибка при закрытии позиций в стратегии {strategy.__class__.__name__}: {e}")
        
        self.logger.info("Все позиции закрыты через стратегии")

    def print_trades(self):
        for order_intent in self._orders:
            self.logger.info(str(order_intent))
    
    def get_strategy_income(self, strategy_class: type) -> float:
        """Возвращает доход конкретной стратегии по классу"""
        for strategy in self._strategies:
            if isinstance(strategy, strategy_class):
                return strategy.income
        return 0.0
    
    def get_strategy_position(self, strategy_class: type) -> int:
        """Возвращает позицию конкретной стратегии по классу"""
        for strategy in self._strategies:
            if isinstance(strategy, strategy_class):
                return strategy.position
        return 0
    
