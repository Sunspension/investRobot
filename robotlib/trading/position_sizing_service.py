"""
Сервис для динамического расчета размера позиции
"""
from datetime import datetime, time
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
        config: PositionSizingConfig = None
    ):
        self._risk_manager = risk_manager
        self._portfolio_manager = portfolio_manager
        self._config = config or PositionSizingConfig()
        self._logger = get_logger(__name__)
    
    async def calculate_position_size(
        self,
        signal: Signal,
        current_position: int,
        figi: str = "FUTIMOEXF000"
    ) -> int:
        """
        Рассчитывает оптимальный размер позиции на основе:
        - Волатильности инструмента
        - Текущего риска портфеля
        - Силы сигнала
        - Времени до закрытия сессии
        
        Args:
            signal: Торговый сигнал
            current_position: Текущая позиция
            figi: FIGI инструмента
            
        Returns:
            Рекомендуемый размер позиции
        """
        # Если динамический расчет отключен, используем фиксированный лимит
        if not self._config.enable_dynamic_sizing:
            return self._calculate_fixed_position_size(current_position, figi)
        
        # 1. Базовый расчет (текущий)
        base_size = await self._calculate_base_position_size(current_position, figi)
        if base_size <= 0:
            return 0
        
        # 2. Коэффициент волатильности (0.5 - 2.0)
        volatility_factor = self._calculate_volatility_factor(signal)
        
        # 3. Коэффициент силы сигнала (0.3 - 1.5)
        signal_strength_factor = self._calculate_signal_strength_factor(signal)
        
        # 4. Коэффициент времени до закрытия (0.5 - 1.0)
        time_factor = self._calculate_time_factor()
        
        # 5. Коэффициент текущего риска (0.7 - 1.0)
        risk_factor = self._calculate_current_risk_factor(current_position)
        
        # 6. Итоговый расчет
        dynamic_size = base_size * volatility_factor * signal_strength_factor * time_factor * risk_factor
        
        # 7. Ограничения
        min_size = self._config.min_position_size
        max_size = int(self._risk_manager.risk_limits.items_per_trade * 
                      self._config.max_position_multiplier)
        
        final_size = int(max(min_size, min(dynamic_size, max_size)))
        
        self._logger.debug(
            f"Расчет размера позиции: base={base_size}, "
            f"vol={volatility_factor:.2f}, signal={signal_strength_factor:.2f}, "
            f"time={time_factor:.2f}, risk={risk_factor:.2f}, final={final_size}"
        )
        
        return final_size
    
    async def _calculate_base_position_size(self, current_position: int, figi: str) -> int:
        """Базовый расчет размера позиции (текущая логика)"""
        current_deposit = await self._portfolio_manager.get_deposit()
        money_limit = current_deposit * (self._risk_manager.risk_limits.percent_from_deposit / 100)
        guarantee_deposit = await self._portfolio_manager.get_guarantee_deposit(figi)
        
        if guarantee_deposit <= 0:
            return 0
        
        frozen_guarantee = current_position * guarantee_deposit
        money_left = money_limit - frozen_guarantee
        return int(money_left // guarantee_deposit)
    
    def _calculate_fixed_position_size(self, current_position: int, figi: str) -> int:
        """Фиксированный расчет размера позиции (старая логика)"""
        return self._risk_manager.risk_limits.items_per_trade
    
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
    
    def _calculate_signal_strength_factor(self, signal: Signal) -> float:
        """Коэффициент силы сигнала"""
        hist_abs = abs(signal.histogram)
        
        if hist_abs > self._config.signal_strength_threshold_strong:
            return self._config.signal_factor_strong
        elif hist_abs > self._config.signal_strength_threshold_medium:
            return self._config.signal_factor_medium
        elif hist_abs > self._config.signal_strength_threshold_weak:
            return self._config.signal_factor_weak
        else:
            return self._config.signal_factor_very_weak
    
    def _calculate_time_factor(self) -> float:
        """Коэффициент времени до закрытия сессии"""
        now = datetime.now().time()
        close_time = time(18, 45)  # Время закрытия
        
        if now >= close_time:
            return self._config.time_factor_close
        elif now >= time(18, 0):
            return self._config.time_factor_last_hour
        else:
            return self._config.time_factor_normal
    
    def _calculate_current_risk_factor(self, current_position: int) -> float:
        """Коэффициент текущего риска портфеля"""
        if current_position == 0:
            return 1.0
        
        # Чем больше позиция, тем осторожнее
        max_allowed = int(self._risk_manager.risk_limits.items_per_trade * 
                         self._config.max_position_multiplier)
        position_ratio = current_position / max_allowed
        return max(self._config.risk_factor_min, 
                  self._config.risk_factor_max - position_ratio * 0.3)
    
    def get_sizing_parameters(self) -> dict:
        """Возвращает текущие параметры расчета размера позиции"""
        return {
            'enable_dynamic_sizing': self._config.enable_dynamic_sizing,
            'min_position_size': self._config.min_position_size,
            'max_position_multiplier': self._config.max_position_multiplier,
            'volatility_threshold_high': self._config.volatility_threshold_high,
            'volatility_threshold_medium': self._config.volatility_threshold_medium,
            'signal_strength_threshold_strong': self._config.signal_strength_threshold_strong,
            'signal_strength_threshold_medium': self._config.signal_strength_threshold_medium,
            'signal_strength_threshold_weak': self._config.signal_strength_threshold_weak,
        }
