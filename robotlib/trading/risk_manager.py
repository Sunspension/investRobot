"""
Модуль для управления рисками в торговле
"""

from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from robotlib.trading.portfolio_manager import PortfolioManager, Position
from robotlib.utils.money import Money
from robotlib.utils.logger import get_logger
from config_data.config import load_config
from robotlib.trading.tinkoff_api_client import TinkoffAPIClient
import asyncio


class RiskLevel(Enum):
    """Уровни риска"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskLimits:
    """Лимиты риска"""
    # Глобальные лимиты (защита от системных рисков)
    max_daily_loss: float # Максимальная дневная потеря (руб)
    trading_enabled: bool = True # Глобальный выключатель торговли
    # Опционально: потолок по суммарному ГО (руб) для инструмента/портфеля
    max_position_go: float | None = None
    # Опционально: максимум открытых позиций
    max_open_positions: int | None = None


@dataclass
class RiskCheck:
    """Результат проверки риска"""
    passed: bool
    risk_level: RiskLevel
    message: str
    recommendation: Optional[str] = None
    code: Optional[str] = None  # машинно-читаемый код нарушения


class RiskManager:
    """Класс для управления рисками"""
    
    def __init__(
        self,
        portfolio_manager: PortfolioManager,
        risk_limits: RiskLimits
    ):
        """
        Инициализация менеджера рисков
        
        Args:
            portfolio_manager: Менеджер портфеля
            risk_limits: Лимиты риска
        """
        self.portfolio_manager = portfolio_manager
        self._risk_limits = risk_limits
        self._logger = get_logger(__name__)
        # История убытков
        self._daily_losses: Dict[str, float] = {}
        self._trade_history: List[Dict] = []
        # Масштаб состояния системы [0..1] и оценка ГО активных заявок (если нет прямых данных)
        self._system_state_scale: float = 1.0
        self._active_orders_go_estimate: float = 0.0
    
    @property
    def risk_limits(self) -> RiskLimits:
        """Возвращает лимиты рисков"""
        return self._risk_limits

    async def get_system_state_scale(self) -> float:
        """Возвращает масштаб состояния системы [0..1] на основе дневной просадки.
        1.0 — нормальный режим, 0.6 — умеренная просадка, 0.3 — сильная, 0.0 — стоп.
        """
        try:
            # Если вручную задан (например, внешней политикой) и он не 1.0 — используем его
            if self._system_state_scale != 1.0:
                return max(0.0, min(1.0, self._system_state_scale))

            max_daily = max(0.0, float(self._risk_limits.max_daily_loss))
            if max_daily <= 0:
                return 1.0
            cur_loss = await self._get_daily_loss()
            ratio = cur_loss / max_daily if max_daily > 0 else 0.0
            if ratio >= 1.0:
                return 0.0
            if ratio >= 0.7:
                return 0.3
            if ratio >= 0.4:
                return 0.6
            return 1.0
        except Exception:
            return 1.0

    def set_system_state_scale(self, value: float) -> None:
        """Позволяет внешне задать масштаб состояния системы [0..1]."""
        self._system_state_scale = max(0.0, min(1.0, float(value)))

    def set_active_orders_go_estimate(self, value: float) -> None:
        """Устанавливает оценку суммарного ГО, занятого активными заявками (руб)."""
        try:
            self._active_orders_go_estimate = max(0.0, float(value))
        except Exception:
            self._active_orders_go_estimate = 0.0

    def get_active_orders_go_estimate(self) -> float:
        """Возвращает оценку суммарного ГО, занятого активными заявками (руб)."""
        return self._active_orders_go_estimate
    
    async def check_trade_risk(
        self,
        figi: str,
        quantity: int,
        direction: str
    ) -> RiskCheck:
        """
        Проверяет риск торговой операции
        
        Args:
            figi: FIGI инструмента
            quantity: Количество лотов
            direction: Направление ("buy" или "sell")
            
        Returns:
            RiskCheck с результатом проверки
        """
        try:
            # 0) Глобальный выключатель
            if not self._risk_limits.trading_enabled:
                return RiskCheck(
                    passed=False,
                    risk_level=RiskLevel.CRITICAL,
                    message="Торговля отключена",
                    recommendation="Включите trading_enabled",
                    code="trading_disabled",
                )

            # 1) Дневные убытки (kill switch)
            daily_loss = await self._get_daily_loss()
            if daily_loss > self._risk_limits.max_daily_loss:
                return RiskCheck(
                    passed=False,
                    risk_level=RiskLevel.CRITICAL,
                    message=f"Дневные убытки {daily_loss:.2f} руб превышают лимит {self._risk_limits.max_daily_loss:.2f} руб",
                    recommendation="Остановить торговлю на сегодня",
                    code="daily_loss_limit_exceeded",
                )

            # 2) Потолок по суммарному ГО (если задан)
            if self._risk_limits.max_position_go is not None:
                per_lot_go = await self.portfolio_manager.get_guarantee_deposit(figi)
                if per_lot_go > 0:
                    current_pos = await self.portfolio_manager.get_position(figi)
                    current_lots = abs(current_pos.quantity) if current_pos else 0
                    new_go = (current_lots + abs(quantity)) * per_lot_go
                    if new_go > float(self._risk_limits.max_position_go):
                        return RiskCheck(
                            passed=False,
                            risk_level=RiskLevel.HIGH,
                            message=f"ГО позиции {new_go:.2f} руб превышает лимит {float(self._risk_limits.max_position_go):.2f} руб",
                            recommendation="Снизьте размер позиции",
                            code="max_position_go_exceeded",
                        )

            # 3) Базовые проверки целостности (продажа больше позиции)
            if direction == "sell":
                if not await self.portfolio_manager.can_sell(figi, quantity):
                    return RiskCheck(
                        passed=False,
                        risk_level=RiskLevel.HIGH,
                        message="Недостаточно лотов для продажи",
                        recommendation="Проверьте размер позиции",
                        code="insufficient_position_for_sell",
                    )

            return RiskCheck(
                passed=True,
                risk_level=RiskLevel.LOW,
                message="Риски в пределах норм",
                recommendation="Разрешено",
                code="ok",
            )
            
        except Exception as e:
            self._logger.error(f"Ошибка проверки риска: {e}")
            return RiskCheck(
                passed=False,
                risk_level=RiskLevel.CRITICAL,
                message=f"Ошибка проверки риска: {e}",
                recommendation="Проверьте настройки"
            )
    
    
    async def get_risk_report(self) -> Dict:
        """
        Получает отчет о рисках
        
        Returns:
            Словарь с информацией о рисках
        """
        try:
            portfolio = await self.portfolio_manager.get_portfolio()
            daily_loss = await self._get_daily_loss()
            
            # Анализ позиций
            risky_positions = []
            for position in portfolio.positions:
                if position.quantity != 0:
                    position_risk = await self._calculate_position_risk(position)
                    if position_risk > 0.1:  # Риск больше 10%
                        risky_positions.append({
                            'figi': position.figi,
                            'risk': position_risk,
                            'quantity': position.quantity,
                            'unrealized_pnl': position.unrealized_pnl
                        })
            
            return {
                'portfolio_value': portfolio.total_amount,
                'available_funds': portfolio.available_amount,
                'daily_loss': daily_loss,
                'risky_positions': risky_positions,
                'risk_limits': {
                    'trading_enabled': self._risk_limits.trading_enabled,
                    'max_daily_loss': self._risk_limits.max_daily_loss,
                    'max_position_go': self._risk_limits.max_position_go,
                    'max_open_positions': self._risk_limits.max_open_positions,
                },
                'recommendations': await self._get_risk_recommendations()
            }
            
        except Exception as e:
            self._logger.error(f"Ошибка получения отчета о рисках: {e}")
            return {}
    
    async def _get_daily_loss(self) -> float:
        """
        Получает дневные убытки
        
        Returns:
            Сумма дневных убытков в рублях
        """
        try:
            today = datetime.now().date()
            today_str = today.strftime('%Y-%m-%d')
            
            if today_str in self._daily_losses:
                return self._daily_losses[today_str]
            
            # Получаем операции за сегодня
            start_of_day = datetime.combine(today, datetime.min.time())
            end_of_day = datetime.combine(today, datetime.max.time())
            
            operations = await self.portfolio_manager.get_operations_history(
                start_of_day, end_of_day
            )
            
            daily_loss = 0.0
            for operation in operations:
                try:
                    payment = getattr(operation, 'payment', 0)
                    # Приводим MoneyValue/Quotation к float
                    payment_float = Money(payment).to_float()
                except Exception:
                    # Фолбэк: если тип неожиданный, пробуем напрямую
                    try:
                        payment_float = float(payment) if payment is not None else 0.0
                    except Exception:
                        payment_float = 0.0

                if payment_float < 0:  # Убыточная операция
                    daily_loss += abs(payment_float)
            
            self._daily_losses[today_str] = daily_loss
            return daily_loss
            
        except Exception as e:
            self._logger.error(f"Ошибка расчета дневных убытков: {e}")
            return 0.0
    
    
    async def _calculate_position_risk(self, position: Position) -> float:
        """
        Рассчитывает риск позиции
        
        Args:
            position: Позиция
            
        Returns:
            Риск позиции в процентах
        """
        try:
            if position.quantity == 0:
                return 0.0
            
            position_value = abs(position.quantity) * position.current_price
            portfolio = await self.portfolio_manager.get_portfolio()
            
            if portfolio.total_amount == 0:
                return 0.0
            
            return (position_value / portfolio.total_amount) * 100
            
        except Exception as e:
            self._logger.error(f"Ошибка расчета риска позиции: {e}")
            return 0.0
    
    def _calculate_trade_risk_level(
        self, 
        trade_value: float, 
        portfolio
    ) -> RiskLevel:
        """
        Рассчитывает уровень риска сделки
        
        Args:
            trade_value: Стоимость сделки
            portfolio: Портфель
            
        Returns:
            Уровень риска
        """
        if portfolio.total_amount == 0:
            return RiskLevel.CRITICAL
        
        trade_percent = (trade_value / portfolio.total_amount) * 100
        
        if trade_percent < 1:
            return RiskLevel.LOW
        elif trade_percent < 5:
            return RiskLevel.MEDIUM
        elif trade_percent < 10:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL
    
    async def _get_risk_recommendations(self) -> List[str]:
        """
        Получает рекомендации по управлению рисками
        
        Returns:
            Список рекомендаций
        """
        recommendations = []
        
        try:
            portfolio = await self.portfolio_manager.get_portfolio()
            daily_loss = await self._get_daily_loss()
            
            # Рекомендации по дневным убыткам
            if daily_loss > self._risk_limits.max_daily_loss * 0.8:
                recommendations.append("Приближаетесь к лимиту дневных убытков")
            
            # Рекомендации по концентрации
            if len(portfolio.positions) > 0:
                max_position_risk = max(
                    await self._calculate_position_risk(pos) 
                    for pos in portfolio.positions 
                    if pos.quantity != 0
                )
                
                if max_position_risk > 20:
                    recommendations.append("Высокая концентрация в одной позиции")
            
        except Exception as e:
            self._logger.error(f"Ошибка получения рекомендаций: {e}")
        
        return recommendations


# Пример использования
async def main():
    """Пример использования RiskManager"""
    logger = get_logger(__name__)
    config = load_config()
    
    # Настройки риска
    risk_limits = RiskLimits(
        max_daily_loss=10000,       # 10k руб
        trading_enabled=True,
        max_position_go=100000,    # 100k руб
        max_open_positions=20
    )
    
    async with TinkoffAPIClient(
        token=config.tcs_client.token,
        account_id=config.tcs_client.account_id,
        sandbox_token=config.tcs_client.sandbox_token
    ) as api_client:
        
        portfolio_manager = PortfolioManager(api_client)
        risk_manager = RiskManager(portfolio_manager, risk_limits)
        
        # Проверяем риск сделки
        risk_check = await risk_manager.check_trade_risk(
            figi="FUTIMOEXF000",
            quantity=1,
            direction="buy"
        )
        
        logger.info(f"Проверка риска: {risk_check.passed}")
        logger.info(f"Уровень риска: {risk_check.risk_level.value}")
        logger.info(f"Сообщение: {risk_check.message}")
        
        # Получаем отчет о рисках
        risk_report = await risk_manager.get_risk_report()
        logger.info(f"Отчет о рисках: {risk_report}")


if __name__ == "__main__":
    asyncio.run(main())
