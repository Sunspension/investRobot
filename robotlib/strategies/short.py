from typing import Optional
from robotlib.utils.money import Money
from robotlib.signal_manager import Signal, Order, OrderIntent, OrderExecution, OrderDirection, OrderType, OrderStatus
from robotlib.strategies.strategy_interface import Strategyable
from robotlib.strategies.interfaces import RiskManageable, PortfolioManageable
from tinkoff.invest import Candle, HistoricCandle

# Константы убраны - значения теперь получаются из API и передаются в initialize()

class ShortStrategy(Strategyable):
    def __init__(
            self, 
            risk_manager: RiskManageable,
            portfolio_manager: PortfolioManageable
    ):
            
        self._position = 0
        self._cost_basis = 0.0
        self._income = 0.0

        self._positions = []
        self._risk_manager = risk_manager
        self._portfolio_manager = portfolio_manager

        self._wait_short_sell_cross = False
        self._wait_short_buy_cross = False
        
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
        Получает от manager-а сигнал (словарь) и решает:
        - открыть шорт
        - закрыть шорт
        - стоп-лосс
        Возвращает список торговых приказов: dict с ключами order/price/qty
        """
        orders = []

        # Обновляем ожидания сигналов
        if signal.peak_detected:
            self._wait_short_sell_cross = True
        if signal.trough_detected:
            self._wait_short_buy_cross = True

        # Проверка стоп-лосса
        stop_loss_orders = self._check_stop_loss(signal.candle)
        orders.extend(stop_loss_orders)

        hist_abs = abs(signal.histogram)

        is_trending_down = signal.macd_prev is not None \
            and signal.signal_prev is not None \
            and signal.macd < signal.signal \
            and signal.macd_prev > signal.signal_prev

        is_crossed_down = signal.macd_prev is not None \
            and signal.signal_prev is not None \
            and signal.macd_prev > signal.signal_prev \
            and signal.macd < signal.signal \
            and hist_abs > 0.1
        is_crossed_up = signal.macd_prev is not None \
            and signal.signal_prev is not None \
            and signal.macd_prev < signal.signal_prev \
            and signal.macd > signal.signal \
            and hist_abs > 0.1

        # Открыть short
        if (self._wait_short_sell_cross and is_crossed_down) or (self._position > 0 and is_trending_down):
            items = await self._items_to_sell_short()
            if items > 0:
                orders.append(
                    OrderIntent(
                        direction=OrderDirection.SELL,
                        quantity=items,
                        order_type=OrderType.MARKET,
                        figi=self._figi
                    )
                )
                self._wait_short_sell_cross = False

        # Закрыть short
        if self._wait_short_buy_cross and is_crossed_up and self._position > 0:
            items = self._items_to_buy_short()
            if items > 0:
                orders.append(
                    OrderIntent(
                        direction=OrderDirection.BUY,
                        quantity=items,
                        order_type=OrderType.MARKET,
                        figi=self._figi
                    )
                )
                self._wait_short_buy_cross = False

        return orders

    
    def close_position(self, candle) -> Optional[OrderIntent]:
        """
        Закрывает все открытые шорт-позиции (покрывает).
        Возвращает OrderIntent для исполнения через OrderExecutor.
        """
        if self._position > 0:
            # Для тестовых данных можем использовать цену из свечи
            # Для реального API цена определится при исполнении
            if candle is not None:
                # Тестовые данные - можем указать примерную цену
                estimated_price = Money(candle.close).to_float()
                order_intent = OrderIntent(
                    direction=OrderDirection.BUY,  # покрываем шорт
                    quantity=self._position,
                    order_type=OrderType.MARKET,  # рыночный ордер
                    figi=self._figi
                )
            else:
                # Реальный API - только намерение
                order_intent = OrderIntent(
                    direction=OrderDirection.BUY,
                    quantity=self._position,
                    order_type=OrderType.MARKET,
                    figi=self._figi
                )
            
            return order_intent
        else:
            return None

    async def _items_to_sell_short(self, figi: str = "FUTIMOEXF000"):
        # Получаем депозит из API
        current_deposit = await self._portfolio_manager.get_deposit()
        # Максимум можно открыть в шорт
        money_limit = current_deposit * (self._risk_manager.risk_limits.percent_from_deposit / 100)
        
        # Получаем гарантийное обеспечение из API
        guarantee_deposit = await self._portfolio_manager.get_guarantee_deposit(figi)
        
        # Заморожено ГО за уже открытые позиции
        frozen_guarantee = self._position * guarantee_deposit
        money_left = money_limit - frozen_guarantee
        # Сколько фьючерсов можем продать в шорт на оставшиеся деньги
        max_items = money_left // guarantee_deposit
        return int(min(max_items, self._risk_manager.risk_limits.items_per_trade))

    def _items_to_buy_short(self):
        return self._position

    def _process_order(self, order: OrderIntent):
        # Этот метод больше не используется для OrderIntent
        # Вместо него используется _process_execution для OrderExecution
        pass
    
    def _process_execution(self, execution: OrderExecution):
        """Обрабатывает исполнение ордера"""
        if execution.intent.direction == OrderDirection.SELL:
            # Открываем шорт
            self._positions.append([execution.executed_price, execution.executed_quantity])
            self._position += execution.executed_quantity
            self._cost_basis += execution.executed_price * execution.executed_quantity
        else:
            # Закрываем шорт
            commission = execution.commission
            self._positions, profit, new_pos = self._fifo_buy_short(
                self._positions, 
                execution.executed_price, 
                execution.executed_quantity, 
                commission
            )
            self._position = new_pos
            self._income += profit

    def _fifo_buy_short(self, positions, price, qty_to_buy, commission=0.0):
        remaining = qty_to_buy
        total_cost = 0.0
        new_positions = []
        for lot_price, lot_qty in positions:
            if remaining == 0:
                new_positions.append([lot_price, lot_qty])
                continue
            buy_qty = min(lot_qty, remaining)
            # Для шорт-стратегии: считаем стоимость открытия (lot_price) для расчета прибыли
            total_cost += lot_price * buy_qty
            remaining -= buy_qty
            if lot_qty > buy_qty:
                new_positions.append([lot_price, lot_qty - buy_qty])

        # Средняя цена открытия шорт-позиций
        avg_open_price = total_cost / qty_to_buy
        # Прибыль = цена открытия - цена закрытия (для шорта)
        price_diff = avg_open_price - price
        # Используем кэшированные значения
        point_value = self._point_value
        contracts_per_lot = self._contracts_per_lot
        gross_profit = price_diff * point_value * contracts_per_lot * qty_to_buy
        # Вычитаем комиссию из прибыли
        net_profit = gross_profit - commission
        new_position_qty = sum(qty for _, qty in new_positions)
        return new_positions, net_profit, new_position_qty

    def _check_stop_loss(self, candle: Candle | HistoricCandle) -> list[OrderIntent]:
        orders = []
        current_price = Money(candle.close).to_float()
        lots_to_cover = []
        for lot_price, lot_qty in self._positions:
            unrealized_loss = current_price - lot_price
            if unrealized_loss >= self._risk_manager.risk_limits.stop_loss_threshold:
                lots_to_cover.append([lot_price, lot_qty])
        if lots_to_cover:
            total_qty = sum(qty for _, qty in lots_to_cover)
            orders.append(
                OrderIntent(
                    direction=OrderDirection.BUY,  # покрываем шорт при стоп-лоссе
                    quantity=total_qty,
                    order_type=OrderType.MARKET,
                    figi=self._figi
                )
            )
        return orders