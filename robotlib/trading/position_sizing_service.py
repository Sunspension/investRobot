"""
Сервис для динамического расчета размера позиции
"""

from robotlib.utils.logger import get_logger
from robotlib.signal_types import Signal
from robotlib.strategies.interfaces import RiskManageable, PortfolioManageable
from robotlib.trading.position_sizing_config import PositionSizingConfig
from robotlib.trading.enums import OperationType, PositionDirection
from robotlib.trading.order_types import OrderDirection


class PositionSizingService:
    """Сервис для динамического расчета размера позиции"""
    
    def __init__(
        self, 
        risk_manager: RiskManageable,
        portfolio_manager: PortfolioManageable,
        config: PositionSizingConfig
    ) -> None:
        self._risk_manager: RiskManageable = risk_manager
        self._portfolio_manager: PortfolioManageable = portfolio_manager
        self._config: PositionSizingConfig = config
        self._logger = get_logger(__name__)
    
    async def calculate_position_size(
        self,
        signal: Signal,
        current_position: int,
        figi: str = "FUTIMOEXF000",
        direction: OrderDirection = OrderDirection.BUY,
        position_direction: PositionDirection = PositionDirection.LONG,
        operation_type: OperationType = OperationType.OPEN
    ) -> int:
        """
        Фьючерсы: размер = min(по ГО, по волатильности) × коэффициент состояния системы,
        с учетом уже открытых позиций/активных заявок.
        
        Args:
            signal: Торговый сигнал
            current_position: Текущая позиция (всегда положительное число)
            figi: FIGI инструмента
            direction: Направление операции (OrderDirection.BUY или OrderDirection.SELL)
            position_direction: Направление текущей позиции (PositionDirection.LONG или PositionDirection.SHORT)
            operation_type: Тип операции (OperationType.OPEN, OperationType.CLOSE, OperationType.INCREASE)
        """
        if not self._config.enable_dynamic_sizing:
            return max(self._config.min_lots, self._risk_manager.risk_limits.items_per_trade)
        
        # Обработка по типу операции
        if operation_type == OperationType.CLOSE:
            # Явное закрытие позиции - закрываем всю позицию
            return current_position
        elif operation_type == OperationType.INCREASE:
            # Увеличение позиции - рассчитываем размер для добавления
            # Проверяем, что направление операции совпадает с направлением позиции
            if (direction == OrderDirection.BUY and position_direction == PositionDirection.LONG) or \
               (direction == OrderDirection.SELL and position_direction == PositionDirection.SHORT):
                # Увеличение позиции - рассчитываем размер по обычной логике
                pass
            else:
                # Неправильное направление для увеличения
                return 0
        elif operation_type == OperationType.OPEN:
            # Новая позиция - рассчитываем размер по обычной логике
            if current_position > 0:
                # Уже есть позиция, но это новая операция - возможно частичное закрытие
                if (direction == OrderDirection.SELL and position_direction == PositionDirection.LONG) or \
                   (direction == OrderDirection.BUY and position_direction == PositionDirection.SHORT):
                    # Противоположное направление - закрытие
                    return current_position
                else:
                    # Одинаковое направление - увеличение
                    pass
            else:
                # Нет позиции - новая позиция
                pass

        # 1) Лимит по ГО (учитывая занятое ГО открытой позицией и активными заявками)
        qty_by_margin: int = await self._calculate_qty_by_margin(current_position, figi)
        if qty_by_margin <= 0:
            self._logger.info("ГО недостаточно для открытия даже 1 лота")
            return 0

        # 2) Ограничение по волатильности
        vol_factor: float = self._calculate_volatility_factor(signal)
        qty_by_vol: int = max(1, int(qty_by_margin * vol_factor))

        # 3) Учет состояния системы/стратегии
        system_scale: float = max(0.0, min(1.0, self._config.system_state_scale))
        qty_scaled: int = max(1, int(qty_by_vol * system_scale)) if qty_by_vol > 0 else 0

        # 4) Жесткие пределы
        final_qty: int = max(self._config.min_lots, min(qty_scaled, self._config.max_lots))

        self._logger.debug(
            f"Sizing figi={figi}: by_margin={qty_by_margin}, vol_factor={vol_factor:.2f}, "
            f"system_scale={system_scale:.2f}, result={final_qty}"
        )

        return final_qty
    
    async def _calculate_qty_by_margin(self, current_position: int, figi: str) -> int:
        """Максимум лотов по доступным средствам и ГО, учитывая открытую позицию и активные заявки."""
        portfolio = await self._portfolio_manager.get_portfolio()
        available_cash: float = portfolio.available_amount
        per_lot_go: float = await self._portfolio_manager.get_guarantee_deposit(figi)
        if per_lot_go <= 0:
            return 0

        # ГО, занятое открытой позицией
        frozen_go_positions: float = abs(current_position) * per_lot_go

        # ГО, занятое активными заявками (если нет точных данных — берем оценку из конфига)
        frozen_go_active: float = self._config.active_orders_go_estimate

        free_for_new: float = max(0.0, available_cash - frozen_go_positions - frozen_go_active)
        if free_for_new < per_lot_go:
            return 0
        return int(free_for_new // per_lot_go)
    
    def _calculate_fixed_position_size(self, current_position: int, figi: str) -> int:
        """Фикс на основе лимита items_per_trade с применением min/max лотов."""
        base: int = self._risk_manager.risk_limits.items_per_trade
        return max(self._config.min_lots, min(base, self._config.max_lots))
    
    def _calculate_volatility_factor(self, signal: Signal) -> float:
        """Коэффициент волатильности на основе ATR или стандартного отклонения"""
        if not hasattr(signal, 'atr') or signal.atr is None:
            return 1.0
        
        # Нормализуем ATR относительно цены
        # Преобразуем Quotation в float
        price: float = signal.candle.close.units + signal.candle.close.nano / 1_000_000_000
        atr_ratio: float = signal.atr / price
        
        if atr_ratio > self._config.volatility_threshold_high:
            return self._config.volatility_factor_high
        elif atr_ratio > self._config.volatility_threshold_medium:
            return self._config.volatility_factor_medium
        else:
            return self._config.volatility_factor_low
    
    # Удалены факторы силы сигнала/времени/риска портфеля по требованию
    
    def get_sizing_parameters(self) -> dict:
        """Возвращает текущие параметры расчета размера позиции"""
        return {
            'enable_dynamic_sizing': self._config.enable_dynamic_sizing,
            'min_lots': self._config.min_lots,
            'max_lots': self._config.max_lots,
            'volatility_threshold_high': self._config.volatility_threshold_high,
            'volatility_threshold_medium': self._config.volatility_threshold_medium,
            'system_state_scale': self._config.system_state_scale,
        }
