"""
Тесты для PositionSizingService
"""
import pytest
from unittest.mock import Mock, AsyncMock
from robotlib.trading.position_sizing_service import PositionSizingService
from robotlib.trading.position_sizing_config import PositionSizingConfig
from robotlib.signal_types import Signal
from robotlib.trading.order_types import OrderDirection, OrderType
from tinkoff.invest import Candle, Quotation


class MockRiskManager:
    def __init__(self, items_per_trade=20, percent_from_deposit=50.0):
        self.risk_limits = Mock()
        self.risk_limits.items_per_trade = items_per_trade
        self.risk_limits.percent_from_deposit = percent_from_deposit


class MockPortfolioManager:
    def __init__(self, deposit=100000, guarantee_deposit=1000):
        self.deposit = deposit
        self.guarantee_deposit = guarantee_deposit
    
    async def get_deposit(self):
        return self.deposit
    
    async def get_guarantee_deposit(self, figi):
        return self.guarantee_deposit


class TestPositionSizingService:
    """Тесты для PositionSizingService"""
    
    @pytest.fixture
    def risk_manager(self):
        return MockRiskManager()
    
    @pytest.fixture
    def portfolio_manager(self):
        return MockPortfolioManager()
    
    @pytest.fixture
    def config(self):
        return PositionSizingConfig()
    
    @pytest.fixture
    def service(self, risk_manager, portfolio_manager, config):
        return PositionSizingService(risk_manager, portfolio_manager, config)
    
    @pytest.fixture
    def mock_signal(self):
        """Создает mock сигнал для тестов"""
        signal = Mock(spec=Signal)
        signal.histogram = 0.2  # Средний сигнал
        signal.atr = None  # Нет ATR
        signal.candle = Mock(spec=Candle)
        signal.candle.close = Quotation(units=2500, nano=0)
        return signal
    
    @pytest.mark.asyncio
    async def test_calculate_position_size_fixed_mode(self, service, mock_signal):
        """Тест расчета размера позиции в фиксированном режиме"""
        # Отключаем динамический расчет
        service._config.enable_dynamic_sizing = False
        
        result = await service.calculate_position_size(
            signal=mock_signal,
            current_position=0,
            figi="FUTIMOEXF000"
        )
        
        # Должен вернуть фиксированный лимит
        assert result == 20  # items_per_trade
    
    @pytest.mark.asyncio
    async def test_calculate_position_size_dynamic_mode(self, service, mock_signal):
        """Тест расчета размера позиции в динамическом режиме"""
        # Включаем динамический расчет
        service._config.enable_dynamic_sizing = True
        
        result = await service.calculate_position_size(
            signal=mock_signal,
            current_position=0,
            figi="FUTIMOEXF000"
        )
        
        # Результат должен быть в разумных пределах
        assert 1 <= result <= 40  # min_position_size <= result <= max_position_multiplier * items_per_trade
        assert isinstance(result, int)
    
    @pytest.mark.asyncio
    async def test_calculate_position_size_with_existing_position(self, service, mock_signal):
        """Тест расчета размера позиции при существующей позиции"""
        result = await service.calculate_position_size(
            signal=mock_signal,
            current_position=10,  # Уже есть позиция
            figi="FUTIMOEXF000"
        )
        
        # Размер должен быть меньше из-за существующей позиции
        assert result >= 1
        assert isinstance(result, int)
    
    @pytest.mark.asyncio
    async def test_calculate_position_size_insufficient_funds(self, service, mock_signal):
        """Тест расчета размера позиции при недостатке средств"""
        # Устанавливаем очень маленький депозит
        service._portfolio_manager.deposit = 100  # Мало денег
        service._portfolio_manager.guarantee_deposit = 1000  # Дорогой инструмент
        
        result = await service.calculate_position_size(
            signal=mock_signal,
            current_position=0,
            figi="FUTIMOEXF000"
        )
        
        # Должен вернуть 0 при недостатке средств
        assert result == 0
    
    def test_volatility_factor_calculation(self, service, mock_signal):
        """Тест расчета коэффициента волатильности"""
        # Тест без ATR
        factor = service._calculate_volatility_factor(mock_signal)
        assert factor == 1.0
        
        # Тест с высокой волатильностью
        mock_signal.atr = 200  # Высокая волатильность (200/2500 = 0.08 > 0.05)
        factor = service._calculate_volatility_factor(mock_signal)
        assert factor == service._config.volatility_factor_high
        
        # Тест со средней волатильностью
        mock_signal.atr = 60  # Средняя волатильность (60/2500 = 0.024)
        factor = service._calculate_volatility_factor(mock_signal)
        assert factor == service._config.volatility_factor_medium
        
        # Тест с низкой волатильностью
        mock_signal.atr = 20  # Низкая волатильность (20/2500 = 0.008)
        factor = service._calculate_volatility_factor(mock_signal)
        assert factor == service._config.volatility_factor_low
    
    def test_signal_strength_factor_calculation(self, service, mock_signal):
        """Тест расчета коэффициента силы сигнала"""
        # Сильный сигнал
        mock_signal.histogram = 0.4
        factor = service._calculate_signal_strength_factor(mock_signal)
        assert factor == service._config.signal_factor_strong
        
        # Средний сигнал
        mock_signal.histogram = 0.25
        factor = service._calculate_signal_strength_factor(mock_signal)
        assert factor == service._config.signal_factor_medium
        
        # Слабый сигнал
        mock_signal.histogram = 0.15
        factor = service._calculate_signal_strength_factor(mock_signal)
        assert factor == service._config.signal_factor_weak
        
        # Очень слабый сигнал
        mock_signal.histogram = 0.05
        factor = service._calculate_signal_strength_factor(mock_signal)
        assert factor == service._config.signal_factor_very_weak
    
    def test_time_factor_calculation(self, service):
        """Тест расчета коэффициента времени"""
        # Этот тест может быть нестабильным из-за зависимости от времени
        # Но мы можем проверить, что возвращается разумное значение
        factor = service._calculate_time_factor()
        assert 0.5 <= factor <= 1.0
    
    def test_risk_factor_calculation(self, service):
        """Тест расчета коэффициента риска"""
        # Нет позиции
        factor = service._calculate_current_risk_factor(0)
        assert factor == 1.0
        
        # Есть позиция
        factor = service._calculate_current_risk_factor(10)
        assert service._config.risk_factor_min <= factor <= 1.0
    
    def test_get_sizing_parameters(self, service):
        """Тест получения параметров расчета"""
        params = service.get_sizing_parameters()
        
        assert 'enable_dynamic_sizing' in params
        assert 'min_position_size' in params
        assert 'max_position_multiplier' in params
        assert 'volatility_threshold_high' in params
        assert 'signal_strength_threshold_strong' in params
