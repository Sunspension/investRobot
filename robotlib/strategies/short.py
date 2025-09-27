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
            position_manager  # PositionManager для FIFO логики (обязательный)
    ):
        self._position = 0
        self._cost_basis = 0.0
        self._income = 0.0

        self._positions = []
        self._position_manager = position_manager  # Новый компонент
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
        stop_loss_orders = await self._check_stop_loss(signal.candle)
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
            items = self._items_to_sell_short(signal)
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

    def _items_to_sell_short(self, signal: Signal, figi: str = "FUTIMOEXF000"):
        # Простая логика расчета размера позиции
        # В будущем можно добавить более сложную логику
        return 1

    def _items_to_buy_short(self):
        return self._position
    
    async def _process_execution(self, execution: OrderExecution):
        """Обрабатывает исполнение ордера"""
        if not execution or (execution.filled_quantity or 0) <= 0:
            return
        if execution.direction == OrderDirection.SELL:
            # Открываем шорт - добавляем в PositionManager
            await self._position_manager.add_to_fifo(
                self._figi, 
                execution.filled_quantity, 
                execution.price, 
                execution.order_id,
                direction='short'
            )
            self._position += execution.filled_quantity
            self._cost_basis += execution.price * execution.filled_quantity
        else:
            # Закрываем шорт - убираем из PositionManager
            await self._position_manager.remove_from_fifo(
                self._figi, 
                execution.filled_quantity
            )
            await self._position_manager.update_position_after_trade(
                self._figi, 
                -execution.filled_quantity, 
                execution.price
            )
            self._position -= execution.filled_quantity


    async def _check_stop_loss(self, candle: Candle | HistoricCandle) -> list[OrderIntent]:
        """Проверяет стоп-лосс для шорт позиций"""
        from robotlib.trading.order_types import OrderIntent, OrderDirection, OrderType
        from robotlib.utils.money import Money
        
        orders = []
        current_price = Money(candle.close).to_float()
        
        # Получаем убыточные позиции от PositionManager
        loss_positions = await self._position_manager.get_loss_positions(
            self._figi, 
            current_price
        )
        
        if loss_positions:
            total_qty = sum(pos.quantity for pos in loss_positions)
            orders.append(OrderIntent(
                direction=OrderDirection.BUY,  # покрываем шорт при стоп-лоссе
                quantity=total_qty,
                order_type=OrderType.MARKET,
                figi=self._figi,
                strategy="stop_loss"
            ))
        
        return orders
