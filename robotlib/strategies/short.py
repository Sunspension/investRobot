from typing import List
from robotlib.utils.logger import get_logger
from robotlib.signal_types import Signal
from robotlib.trading.order_types import OrderIntent, OrderDirection, OrderType
from robotlib.strategies.strategy_interface import Strategyable
from robotlib.trading.position_sync_interface import PositionContext
from robotlib.trading.position_sizing_service import PositionSizingService
from robotlib.trading.enums import OperationType, PositionDirection


class ShortStrategy(Strategyable):
    def __init__(self, figi: str, position_sizing_service: PositionSizingService) -> None:
        self._logger = get_logger(__name__)
        self._wait_short_sell_cross: bool = False
        self._wait_short_buy_cross: bool = False
        self._figi: str = figi
        self._position_sizing_service: PositionSizingService = position_sizing_service

    @property
    def strategy_name(self) -> str:
        return self.__class__.__name__
    
    def initialize(
        self, 
        point_value: float,
        contracts_per_lot: int,
        figi: str = "FUTIMOEXF000"
    ) -> None:
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

    async def execute(self, signal: Signal, position_context: PositionContext) -> List[OrderIntent]:
        """
        Получает от manager-а сигнал (словарь) и решает:
        - открыть шорт
        - закрыть шорт
        - стоп-лосс
        Возвращает список торговых приказов: dict с ключами order/price/qty
        """
        orders: List[OrderIntent] = []

        # Обновляем ожидания сигналов
        if signal.peak_detected:
            self._wait_short_sell_cross = True
        if signal.trough_detected:
            self._wait_short_buy_cross = True

        # Стоп-лосс логика централизована в PositionManager

        hist_abs: float = abs(signal.histogram)
        try:
            self._logger.info(
                f"Short.execute: pos={position_context.quantity} macd={getattr(signal,'macd',None):.4f} "
                f"sig={getattr(signal,'signal',None):.4f} hist={getattr(signal,'histogram',None):.4f} "
                f"peak={getattr(signal,'peak_detected',False)} trough={getattr(signal,'trough_detected',False)}"
            )
        except Exception:
            pass

        # Анализ тренда для увеличения шорта: если позиция открыта и тренд усиливается (цена падает)
        is_trending_down: bool = (
            signal.macd_prev is not None
            and signal.signal_prev is not None
            and signal.macd < signal.signal
            and signal.macd_prev > signal.signal_prev
        )

        is_crossed_down: bool = (
            signal.macd_prev is not None
            and signal.signal_prev is not None
            and signal.macd_prev > signal.signal_prev
            and signal.macd < signal.signal
            and hist_abs > 0.01
        )
        is_crossed_up: bool = (
            signal.macd_prev is not None
            and signal.signal_prev is not None
            and signal.macd_prev < signal.signal_prev
            and signal.macd > signal.signal
            and hist_abs > 0.01
        )

        # Открыть short: ждём peak и пересечения вниз; увелечение шорта при тренде
        if (self._wait_short_sell_cross and is_crossed_down) or (position_context.quantity > 0 and is_trending_down):
            # Запрашиваем размер позиции у PositionSizingService для открытия шорта
            quantity: int = await self._position_sizing_service.calculate_position_size(
                signal=signal,
                current_position=position_context.quantity,
                figi=self._figi,
                direction=OrderDirection.SELL,
                position_direction=PositionDirection.SHORT,
                operation_type=OperationType.OPEN if position_context.quantity == 0 else OperationType.INCREASE
            )
            if quantity > 0:
                orders.append(
                    OrderIntent(
                        direction=OrderDirection.SELL,
                        quantity=quantity,
                        order_type=OrderType.MARKET,
                        figi=self._figi,
                        strategy=self.strategy_name,
                    )
                )
                self._wait_short_sell_cross = False
                self._logger.info(f"Short: SELL intent qty={quantity}")
            else:
                self._logger.info("Short: qty<=0, пропускаем SELL")

        # Закрыть short: ждём trough и пересечения вверх
        if self._wait_short_buy_cross and is_crossed_up and position_context.quantity > 0:
            # Запрашиваем размер позиции у PositionSizingService для закрытия шорта
            items: int = await self._position_sizing_service.calculate_position_size(
                signal=signal,
                current_position=position_context.quantity,
                figi=self._figi,
                direction=OrderDirection.BUY,
                position_direction=PositionDirection.SHORT,
                operation_type=OperationType.CLOSE
            )
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

    
