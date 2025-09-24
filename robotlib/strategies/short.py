from typing import Optional
from robotlib.utils.money import Money
from robotlib.utils.logger import get_logger
from robotlib.signal_types import Signal
from robotlib.trading.order_types import OrderIntent, OrderExecution, OrderDirection, OrderType, OrderStatus
from robotlib.strategies.strategy_interface import Strategyable
from robotlib.strategies.interfaces import RiskManageable, PortfolioManageable, PositionSizingManageable
from tinkoff.invest import Candle, HistoricCandle

class ShortStrategy(Strategyable):
    def __init__(
            self, 
            risk_manager: RiskManageable,
            portfolio_manager: PortfolioManageable,
            position_sizing_service: PositionSizingManageable
    ):
            
        self._position = 0
        self._cost_basis = 0.0
        self._income = 0.0

        self._positions = []
        self._risk_manager = risk_manager
        self._portfolio_manager = portfolio_manager
        self._position_sizing_service = position_sizing_service
        self._logger = get_logger(__name__)

        self._wait_short_sell_cross = False
        self._wait_short_buy_cross = False
        
        # Кэшированные значения
        self._point_value: Optional[float] = None
        self._contracts_per_lot: Optional[int] = None
        self._figi: str = "FUTIMOEXF000"

    @property
    def strategy_name(self) -> str:
        return self.__class__.__name__
    
    def initialize(
        self, 
        point_value: float,
        contracts_per_lot: int,
        figi: str = "FUTIMOEXF000"
    ):
        """
        Инициализирует кэшированные значения при старте торговли
        
        Args:
            figi: FIGI инструмента для торговли
            point_value: Стоимость одного пункта (получена из API)
            contracts_per_lot: Количество контрактов в лоте (получено из API)
        """
        self._figi = figi
        
        # Используем переданные значения
        self._point_value = point_value
        self._contracts_per_lot = contracts_per_lot

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
        try:
            self._logger.info(
                f"Short.execute: pos={self._position} macd={getattr(signal,'macd',None):.4f} "
                f"sig={getattr(signal,'signal',None):.4f} hist={getattr(signal,'histogram',None):.4f} "
                f"peak={getattr(signal,'peak_detected',False)} trough={getattr(signal,'trough_detected',False)}"
            )
        except Exception:
            pass

        # Анализ тренда для увеличения шорта: если позиция открыта и тренд усиливается (цена падает)
        is_trending_down = (
            signal.macd_prev is not None
            and signal.signal_prev is not None
            and signal.macd < signal.signal
            and signal.macd_prev > signal.signal_prev
        )

        is_crossed_down = (
            signal.macd_prev is not None
            and signal.signal_prev is not None
            and signal.macd_prev > signal.signal_prev
            and signal.macd < signal.signal
            and hist_abs > 0.01
        )
        is_crossed_up = (
            signal.macd_prev is not None
            and signal.signal_prev is not None
            and signal.macd_prev < signal.signal_prev
            and signal.macd > signal.signal
            and hist_abs > 0.01
        )

        # Открыть short: ждём peak и пересечения вниз; увелечение шорта при тренде
        if (self._wait_short_sell_cross and is_crossed_down) or (self._position > 0 and is_trending_down):
            items = await self._items_to_sell_short(signal)
            if items > 0:
                orders.append(
                    OrderIntent(
                        direction=OrderDirection.SELL,
                        quantity=items,
                        order_type=OrderType.MARKET,
                        figi=self._figi,
                        strategy=self.strategy_name,
                    )
                )
                self._wait_short_sell_cross = False
                self._logger.info(f"Short: SELL intent qty={items}")
            else:
                self._logger.info("Short: qty<=0, пропускаем SELL")

        # Закрыть short: ждём trough и пересечения вверх
        if self._wait_short_buy_cross and is_crossed_up and self._position > 0:
            items = self._items_to_buy_short()
            if items > 0:
                orders.append(
                    OrderIntent(
                        direction=OrderDirection.BUY,
                        quantity=items,
                        order_type=OrderType.MARKET,
                        figi=self._figi,
                        strategy=self.strategy_name,
                    )
                )
                self._wait_short_buy_cross = False
                self._logger.info(f"Short: BUY intent qty={items}")
            else:
                self._logger.info("Short: qty<=0, пропускаем BUY")

        if not orders:
            self._logger.info("Short: условий для входа/выхода нет")
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
                    figi=self._figi,
                    strategy=self.strategy_name,
                )
            else:
                # Реальный API - только намерение
                order_intent = OrderIntent(
                    direction=OrderDirection.BUY,
                    quantity=self._position,
                    order_type=OrderType.MARKET,
                    figi=self._figi,
                    strategy=self.strategy_name,
                )
            
            return order_intent
        else:
            return None

    async def _items_to_sell_short(self, signal: Signal, figi: str = "FUTIMOEXF000"):
        return await self._position_sizing_service.calculate_position_size(
            signal=signal,
            current_position=self._position,
            figi=figi
        )

    def _items_to_buy_short(self):
        return self._position
    
    def _process_execution(self, execution: OrderExecution):
        """Обрабатывает исполнение ордера"""
        if not execution or (execution.filled_quantity or 0) <= 0:
            return
        if execution.direction == OrderDirection.SELL:
            # Открываем шорт
            self._positions.append([execution.price, execution.filled_quantity])
            self._position += execution.filled_quantity
            self._cost_basis += execution.price * execution.filled_quantity
        else:
            # Закрываем шорт
            commission = execution.commission
            self._positions, profit, new_pos = self._fifo_buy_short(
                self._positions, 
                execution.price, 
                execution.filled_quantity, 
                commission
            )
            self._position = new_pos
            self._income += profit

    def _fifo_buy_short(self, positions, price, qty_to_buy, commission=0.0):
        if qty_to_buy <= 0:
            new_position_qty = sum(qty for _, qty in positions)
            return positions, 0.0, new_position_qty
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
