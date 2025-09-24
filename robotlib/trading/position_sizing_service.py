"""
Сервис для динамического расчета размера позиции
"""
from typing import Optional
from robotlib.utils.logger import get_logger
from robotlib.signal_types import Signal
from robotlib.strategies.interfaces import RiskManageable, PortfolioManageable
from robotlib.trading.position_sizing_config import PositionSizingConfig


class PositionSizingService:
    """Сервис для динамического расчета размера позиции"""
    
    def __init__(
        self, 
        risk_manager: RiskManageable,
        portfolio_manager: PortfolioManageable,
        config: PositionSizingConfig
    ):
        self._risk_manager = risk_manager
        self._portfolio_manager = portfolio_manager
        self._config = config
        self._logger = get_logger(__name__)
    
    async def calculate_position_size(
        self,
        signal: Signal,
        current_position: int,
        figi: str = "FUTIMOEXF000"
    ) -> int:
        """
        Фьючерсы: размер = min(по ГО, по волатильности) × коэффициент состояния системы,
        с учетом уже открытых позиций/активных заявок.
        """
        if not self._config.enable_dynamic_sizing:
            return max(self._config.min_lots, self._risk_manager.risk_limits.items_per_trade)

        # 1) Лимит по ГО (учитывая занятое ГО открытой позицией и активными заявками)
        qty_by_margin = await self._calculate_qty_by_margin(current_position, figi)
        if qty_by_margin <= 0:
            self._logger.info("ГО недостаточно для открытия даже 1 лота")
            return 0

        # 2) Ограничение по волатильности
        vol_factor = self._calculate_volatility_factor(signal)
        qty_by_vol = max(1, int(qty_by_margin * vol_factor))

        # 3) Учет состояния системы/стратегии
        system_scale = max(0.0, min(1.0, self._config.system_state_scale))
        qty_scaled = max(1, int(qty_by_vol * system_scale)) if qty_by_vol > 0 else 0

        # 4) Жесткие пределы
        final_qty = max(self._config.min_lots, min(qty_scaled, self._config.max_lots))

        self._logger.debug(
            f"Sizing figi={figi}: by_margin={qty_by_margin}, vol_factor={vol_factor:.2f}, "
            f"system_scale={system_scale:.2f}, result={final_qty}"
        )

        return final_qty
    
    async def _calculate_qty_by_margin(self, current_position: int, figi: str) -> int:
        """Максимум лотов по доступным средствам и ГО, учитывая открытую позицию и активные заявки."""
        portfolio = await self._portfolio_manager.get_portfolio()
        available_cash = portfolio.available_amount
        per_lot_go = await self._portfolio_manager.get_guarantee_deposit(figi)
        if per_lot_go <= 0:
            return 0

        # ГО, занятое открытой позицией
        frozen_go_positions = abs(current_position) * per_lot_go

        # ГО, занятое активными заявками (если нет точных данных — берем оценку из конфига)
        frozen_go_active = self._config.active_orders_go_estimate

        free_for_new = max(0.0, available_cash - frozen_go_positions - frozen_go_active)
        if free_for_new < per_lot_go:
            return 0
        return int(free_for_new // per_lot_go)
    
    def _calculate_fixed_position_size(self, current_position: int, figi: str) -> int:
        """Фикс на основе лимита items_per_trade с применением min/max лотов."""
        base = self._risk_manager.risk_limits.items_per_trade
        return max(self._config.min_lots, min(base, self._config.max_lots))
    
    def _calculate_volatility_factor(self, signal: Signal) -> float:
        """Коэффициент волатильности на основе ATR или стандартного отклонения"""
        if not hasattr(signal, 'atr') or signal.atr is None:
            return 1.0
        
        # Нормализуем ATR относительно цены
        # Преобразуем Quotation в float
        price = signal.candle.close.units + signal.candle.close.nano / 1_000_000_000
        atr_ratio = signal.atr / price
        
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
