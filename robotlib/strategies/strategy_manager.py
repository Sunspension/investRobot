import pandas as pd

from typing import List
from dataclasses import asdict
from pandas import DataFrame
from robotlib.signal_manager import SignalManager
from robotlib.trading.order_types import OrderIntent
from robotlib.strategies.strategy_interface import Strategyable
from robotlib.trading.interfaces import StrategyManageable, OrderExecutable
from robotlib.strategies.signal_dispatcher import SignalDispatchable
from robotlib.utils.logger import get_logger
from robotlib.utils.money import Money
from tinkoff.invest import Candle, HistoricCandle
from robotlib.strategies.intent_arbiter_interfaces import IntentArbiterable

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
        strategies: List[Strategyable],
        intent_arbiter: IntentArbiterable,
        order_executor: OrderExecutable,
        signal_dispatcher: SignalDispatchable,
        position_manager,  # PositionManager для проверки стоп-лоссов
    ):
        self._signal_manager = signal_manager
        self._risk_manager = risk_manager
        self._portfolio_manager = portfolio_manager
        self._order_executor = order_executor
        self._signal_dispatcher = signal_dispatcher
        self._position_manager = position_manager
        self._orders = []
        self._logger = get_logger(__name__)
        self._last_processed_bar_time = None
        self._strategies = strategies
        self._intent_arbiter: IntentArbiterable = intent_arbiter

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
                strategy.initialize(point_value=point_value, contracts_per_lot=contracts_per_lot, figi=figi)

    async def on_candle(self, candle: Candle | HistoricCandle):
        # Обрабатываем только закрытую свечу и не более одного раза на бар
        try:
            if hasattr(candle, 'is_complete') and not getattr(candle, 'is_complete'):
                return
        except Exception:
            pass
        bar_time = getattr(candle, 'time', None)
        if bar_time is not None and self._last_processed_bar_time == bar_time:
            return

        self._logger.debug(f"on_candle: получена свеча {bar_time}")
        signal = self._signal_manager.add_candle(candle)
        if not signal:
            return
        # Отправляем сигнал в диспетчер
        try:
            price = Money(candle.close).to_float()
        except Exception:
            price = 0.0
        await self._signal_dispatcher.dispatch_signal(signal, getattr(candle, 'figi', 'unknown'), price)

        # Выполняем все стратегии и собираем intents в арбитр
        intents_bucket: list[OrderIntent] = []

        # Получаем контекст позиции для текущего инструмента
        figi = getattr(candle, 'figi', 'unknown')
        position_context = None
        if self._position_manager and figi != 'unknown':
            try:
                position_context = await self._position_manager.get_position_context(figi)
            except Exception as e:
                self._logger.warning(f"Не удалось получить контекст позиции для {figi}: {e}")
        
        # Если контекст не получен, создаем пустой
        if position_context is None:
            from robotlib.trading.position_sync_interface import PositionContext
            from datetime import datetime
            position_context = PositionContext(
                figi=figi,
                quantity=0,
                avg_price=0.0,
                has_position=False,
                direction='',
                last_updated=datetime.now()
            )

        for strategy in self._strategies:
            self._logger.debug(f"execute: {strategy.__class__.__name__} processing signal hist={getattr(signal,'histogram',None)}")
            order_intents: list[OrderIntent] = await strategy.execute(signal, position_context)
            self._logger.debug(f"execute: {strategy.__class__.__name__} вернул {len(order_intents)} намерений")
            intents_bucket.extend(order_intents)
        
        # Централизованная проверка стоп-лосс через PositionManager
        if self._position_manager and figi != 'unknown':
            try:
                current_price = Money(candle.close).to_float()
                stop_loss_orders = await self._check_stop_losses(figi, current_price)
                intents_bucket.extend(stop_loss_orders)
            except Exception as e:
                self._logger.error(f"Ошибка проверки стоп-лосса для {figi}: {e}")
        
        self._intent_arbiter.add_intents(intents_bucket)
        netted_intents = self._intent_arbiter.flush()

        # Исполнение
        for order_intent in netted_intents:
            try:
                self._logger.info(f"Arbiter Intent → исполнение: {order_intent}")
                execution = await self._order_executor.execute_order(order_intent)
                self._logger.info(f"Ордер выполнен: {execution}")
            except Exception as e:
                self._logger.error(f"Ошибка выполнения ордера {order_intent}: {e}")

        # Отмечаем свечу как обработанную
        self._last_processed_bar_time = bar_time

    async def warmup_with_bars(self, bars: list[dict], *, dispatch_signals: bool = True, place_orders: bool = False):
        """Прогревает индикаторы историческими барами без размещения ордеров.

        bars: [{'time': dt, 'open': float, 'high': float, 'low': float, 'close': float}]
        dispatch_signals: если True — отправляем сигналы в визуализатор для счетчиков, но ордера не размещаем
        place_orders: должен быть False на прогреве
        """
        for b in bars:
            sig = self._signal_manager.add_bar_values(
                time=b['time'],
                open_price=b['open'],
                high_price=b['high'],
                low_price=b['low'],
                close_price=b['close'],
            )
            if sig and dispatch_signals:
                try:
                    await self._signal_dispatcher.dispatch_signal(sig, 'unknown', float(b['close']))
                except Exception:
                    pass
            if place_orders and self._order_executor:
                # На прогреве мы не создаём ордеров
                pass
    
    def close_position(self, candle: Candle | HistoricCandle):
        # Закрываем позиции во всех стратегиях
        for strategy in self._strategies:
            order_intent = strategy.close_position(candle)
            if order_intent:
                self._orders.append(order_intent)
    
    
    async def close_all_positions(self) -> None:
        """Закрывает все позиции во всех стратегиях"""
        self._logger.info("Закрытие всех позиций через стратегии...")
        
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
                                await strategy._process_execution(execution)
                            
                            self._logger.info(f"Позиция закрыта в стратегии {strategy.__class__.__name__}: {execution}")
                            
                        except Exception as e:
                            self._logger.error(f"Ошибка выполнения ордера закрытия позиции: {e}")
                    else:
                        # Если нет OrderExecutor, просто сохраняем намерение
                        self._orders.append(order_intent)
                        self._logger.info(f"Закрыта позиция в стратегии {strategy.__class__.__name__}")
                        
            except Exception as e:
                self._logger.error(f"Ошибка при закрытии позиций в стратегии {strategy.__class__.__name__}: {e}")
        
        self._logger.info("Все позиции закрыты через стратегии")

    def print_trades(self):
        for order_intent in self._orders:
            self._logger.info(str(order_intent))
    
    
    
    async def _check_stop_losses(self, figi: str, current_price: float) -> list[OrderIntent]:
        """Централизованная проверка стоп-лосс через PositionManager"""
        from robotlib.trading.order_types import OrderIntent, OrderDirection, OrderType
        
        orders = []
        
        # Получаем убыточные позиции от PositionManager
        loss_positions = await self._position_manager.get_loss_positions(figi, current_price)
        
        if loss_positions:
            total_qty = sum(pos.quantity for pos in loss_positions)
            
            # Определяем направление закрытия на основе направления позиции
            position_direction = await self._position_manager.get_position_direction(figi)
            if position_direction == 'long':
                # Закрываем лонг - продаем
                direction = OrderDirection.SELL
            else:  # short
                # Закрываем шорт - покупаем
                direction = OrderDirection.BUY
            
            orders.append(OrderIntent(
                direction=direction,
                quantity=total_qty,
                order_type=OrderType.MARKET,
                figi=figi,
                strategy="stop_loss"
            ))
            
            self._logger.info(f"🛡️ Стоп-лосс: {direction.value} {total_qty} {figi} при цене {current_price}")
        
        return orders
    
    
    
