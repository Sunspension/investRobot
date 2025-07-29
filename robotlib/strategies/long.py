from typing import Optional
from robotlib.utils.money import Money
from robotlib.signal_manager import Signal, Order, OrderIntent, OrderExecution, OrderDirection, OrderType, OrderStatus
from robotlib.strategies.strategy_interface import Strategyable
from robotlib.strategies.interfaces import RiskManageable, PortfolioManageable
from tinkoff.invest import Candle, HistoricCandle

# Константы убраны - значения теперь получаются из API и передаются в initialize()

class LongStrategy(Strategyable):
    def __init__(
            self, 
            risk_manager: RiskManageable,
            portfolio_manager: PortfolioManageable
    ):
            
        self._position = 0
        self._cost_basis = 0.0
        self._income = 0.0

        self._positions = []  # список [price, quantity]
        self._risk_manager = risk_manager
        self._portfolio_manager = portfolio_manager

        self._wait_buy_cross = False
        self._wait_sell_cross = False
        
        # Кэшированные значения
        self._point_value: Optional[float] = None
        self._contracts_per_lot: Optional[int] = None
        self._figi: str = "FUTIMOEXF000"

    @property
    def strategy_name(self) -> str:
        return self.__class__.__name__
    
    async def initialize(self, figi: str = "FUTIMOEXF000", point_value: float = None, contracts_per_lot: int = None) -> None:
        """
        Инициализирует кэшированные значения при старте торговли
        
        Args:
            figi: FIGI инструмента для торговли
            point_value: Стоимость одного пункта (получена из API)
            contracts_per_lot: Количество контрактов в лоте (получено из API)
        """
        self._figi = figi
        
        # Используем переданные значения или fallback к значениям по умолчанию
        self._point_value = point_value if point_value and point_value > 0 else 10.0  # Fallback: 10 руб за пункт
        self._contracts_per_lot = contracts_per_lot if contracts_per_lot and contracts_per_lot > 0 else 10  # Fallback: 10 контрактов в лоте
    
    async def execute(self, signal: Signal) -> list[OrderIntent]:
        """
        Получает от manager-а сигнал и решает:
        - открыть лонг
        - закрыть лонг
        - стоп-лосс
        Возвращает список торговых приказов: dict с ключами order/price/qty
        """
        orders = []

        # Обновляем ожидания сигналов
        if signal.trough_detected:
            self._wait_buy_cross = True
        if signal.peak_detected:
            self._wait_sell_cross = True

        # Проверка стоп-лосса
        stop_loss_orders = self._check_stop_loss(signal.candle)
        orders.extend(stop_loss_orders)

        hist_abs = abs(signal.histogram)
        
        # Анализ тренда для дозакупки: если позиция открыта и тренд усиливается (цена растёт)
        is_trending_up = signal.macd_prev is not None \
            and signal.signal_prev is not None \
            and signal.macd > signal.signal \
            and signal.macd_prev < signal.signal_prev

        is_crossed_up = signal.macd_prev is not None \
            and signal.signal_prev is not None \
            and signal.macd_prev < signal.signal_prev \
            and signal.macd > signal.signal \
            and hist_abs > 0.1

        is_crossed_down = signal.macd_prev is not None \
            and signal.signal_prev is not None \
            and signal.macd_prev > signal.signal_prev \
            and signal.macd < signal.signal \
            and hist_abs > 0.1

        # Открыть позицию
        if (self._wait_buy_cross and is_crossed_up) or (self._position > 0 and is_trending_up):
            items = await self._items_to_buy()
            if items > 0:
                orders.append(
                    OrderIntent(
                        direction=OrderDirection.BUY,
                        quantity=items,
                        order_type=OrderType.MARKET,
                        figi=self._figi
                    )
                )
                self._wait_buy_cross = False

        # Закрыть позицию
        if self._wait_sell_cross and is_crossed_down and self._position > 0:
            items = self._items_to_sell()
            if items > 0:
                orders.append(
                    OrderIntent(
                        direction=OrderDirection.SELL,
                        quantity=items,
                        order_type=OrderType.MARKET,
                        figi=self._figi
                    )
                )
                self._wait_sell_cross = False

        return orders
    
    def close_position(self, candle) -> Optional[OrderIntent]:
        """
        Закрывает все открытые лонг-позиции.
        Возвращает OrderIntent для исполнения через OrderExecutor.
        """
        if self._position > 0:
            return OrderIntent(
                direction=OrderDirection.SELL,
                quantity=self._position,
                order_type=OrderType.MARKET,
                figi=self._figi
            )
        else:
            return None

    async def _items_to_buy(self, figi: str = "FUTIMOEXF000"):
        # Получаем депозит из API
        current_deposit = await self._portfolio_manager.get_deposit()
        money_limit = current_deposit * (self._risk_manager.risk_limits.percent_from_deposit / 100)
        
        # Получаем гарантийное обеспечение из API
        guarantee_deposit = await self._portfolio_manager.get_guarantee_deposit(figi)
        
        # Заморожено ГО за уже открытые позиции
        frozen_guarantee = self._position * guarantee_deposit
        money_left = money_limit - frozen_guarantee
        # Сколько фьючерсов можем купить на оставшиеся деньги
        max_items = money_left // guarantee_deposit
        return int(min(max_items, self._risk_manager.risk_limits.items_per_trade))

    def _items_to_sell(self):
        return self._position

    def _process_order(self, order: OrderIntent):
        # Этот метод больше не используется для OrderIntent
        # Вместо него используется _process_execution для OrderExecution
        pass
    
    def _process_execution(self, execution: OrderExecution):
        """Обрабатывает исполнение ордера"""
        if execution.intent.direction == OrderDirection.BUY:
            # Открываем лонг
            self._positions.append([execution.executed_price, execution.executed_quantity])
            self._position += execution.executed_quantity
            self._cost_basis += execution.executed_price * execution.executed_quantity
        else:
            # Закрываем лонг
            commission = execution.commission
            self._positions, profit, new_pos = self._fifo_sell(
                self._positions, 
                execution.executed_price, 
                execution.executed_quantity, 
                commission
            )
            self._position = new_pos
            self._income += profit

    def _fifo_sell(self, positions, price, qty_to_sell, commission=0.0):
        remaining = qty_to_sell
        total_cost = 0.0
        new_positions = []
        for lot_price, lot_qty in positions:
            if remaining == 0:
                new_positions.append([lot_price, lot_qty])
                continue
            sell_qty = min(lot_qty, remaining)
            # Для лонг-стратегии: считаем стоимость открытия (lot_price) для расчета прибыли
            total_cost += lot_price * sell_qty
            remaining -= sell_qty
            if lot_qty > sell_qty:
                new_positions.append([lot_price, lot_qty - sell_qty])
        
        # Средняя цена открытия лонг-позиций
        avg_open_price = total_cost / qty_to_sell
        # Прибыль = цена закрытия - цена открытия (для лонга)
        price_diff = price - avg_open_price
        # Используем кэшированные значения
        point_value = self._point_value
        contracts_per_lot = self._contracts_per_lot
        gross_profit = price_diff * point_value * contracts_per_lot * qty_to_sell
        # Вычитаем комиссию из прибыли
        net_profit = gross_profit - commission
        new_position_qty = sum(qty for _, qty in new_positions)
        return new_positions, net_profit, new_position_qty

    def _check_stop_loss(self, candle: Candle | HistoricCandle) -> list[OrderIntent]:
        orders = []
        current_price = Money(candle.close).to_float()
        lots_to_close = []
        for lot_price, lot_qty in self._positions:
            unrealized_loss = lot_price - current_price
            if unrealized_loss >= self._risk_manager.risk_limits.stop_loss_threshold:
                lots_to_close.append([lot_price, lot_qty])
        if lots_to_close:
            total_qty = sum(qty for _, qty in lots_to_close)
            orders.append(
                OrderIntent(
                    direction=OrderDirection.SELL,  # продаем при стоп-лоссе
                    quantity=total_qty,
                    order_type=OrderType.MARKET,
                    figi=self._figi
                )
            )
        return orders
    