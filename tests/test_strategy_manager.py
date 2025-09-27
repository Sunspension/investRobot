"""
Исправленные тесты для StrategyManager
"""
import unittest
import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio
from datetime import datetime

from robotlib.strategies.strategy_manager import StrategyManager
from robotlib.strategies.intent_arbiter import SimpleIntentArbiter
from robotlib.strategies.signal_dispatcher import NullSignalDispatcher
from robotlib.signal_manager import Signal
from robotlib.trading.order_types import OrderIntent, OrderDirection, OrderType
from robotlib.trading.position_sync_interface import PositionContext
from robotlib.strategies.long import LongStrategy
from tests.mocks import MockRiskManager, MockPortfolioManager
from tinkoff.invest import Quotation


def create_position_context(figi: str = "FUTIMOEXF000", quantity: int = 0, avg_price: float = 0.0, 
                           has_position: bool = False, direction: str = '') -> PositionContext:
    """Создание мока PositionContext для тестов"""
    return PositionContext(
        figi=figi,
        quantity=quantity,
        avg_price=avg_price,
        has_position=has_position,
        direction=direction,
        last_updated=datetime.now()
    )


class TestStrategyManager(unittest.TestCase):
    """Исправленные тесты для StrategyManager"""
    
    def setUp(self):
        """Настройка тестов"""
        self.mock_portfolio_manager = MockPortfolioManager(deposit=100000.0, guarantee_deposit=1700.0)
        self.mock_signal_manager = Mock()
        self.mock_risk_manager = MockRiskManager(
            percent_from_deposit=50.0,
            items_per_trade=20,
            stop_loss_threshold=8.0
        )
        
        # Создаем мок стратегии
        self.mock_strategies = [Mock(), Mock()]
        for strategy in self.mock_strategies:
            strategy.execute = AsyncMock(return_value=[])
            strategy._figi = "FUTIMOEXF000"
        
        # Создаем мок PositionManager
        self.mock_position_manager = Mock()
        self.mock_position_manager.get_stop_loss_positions = AsyncMock(return_value={})
        self.mock_position_manager.get_position_direction = Mock(return_value='long')
        self.mock_position_manager.get_position_context = AsyncMock(return_value=create_position_context())
        
        self.strategy_manager = StrategyManager(
            signal_manager=self.mock_signal_manager,
            risk_manager=self.mock_risk_manager,
            portfolio_manager=self.mock_portfolio_manager,
            strategies=self.mock_strategies,
            intent_arbiter=SimpleIntentArbiter(),
            order_executor=Mock(),
            signal_dispatcher=NullSignalDispatcher(),
            position_manager=self.mock_position_manager,
        )
    
    def test_init(self):
        """Тест инициализации"""
        self.assertEqual(self.strategy_manager._portfolio_manager, self.mock_portfolio_manager)
        self.assertEqual(self.strategy_manager._signal_manager, self.mock_signal_manager)
        self.assertEqual(self.strategy_manager._risk_manager, self.mock_risk_manager)
        self.assertEqual(len(self.strategy_manager._strategies), 2)
        # _orders - это теперь переменная экземпляра
        self.assertIsNotNone(self.strategy_manager._orders)
        self.assertEqual(len(self.strategy_manager._orders), 0)
    
    @pytest.mark.asyncio

    
    async def test_on_candle_no_signal(self):
        """Тест обработки свечи без сигнала"""
        # Создаем мок свечи
        mock_candle = Mock()
        mock_candle.close = Quotation(units=100, nano=0)
        mock_candle.time = datetime.now()
        
        # Мокаем signal_manager, чтобы он не возвращал сигнал
        self.mock_signal_manager.add_candle = Mock(return_value=None)
        
        await self.strategy_manager.on_candle(mock_candle)
        
        # Проверяем, что заказы не добавились (используем переменную экземпляра)
        self.assertEqual(len(self.strategy_manager._orders), 0)
    
    @pytest.mark.asyncio

    
    async def test_on_candle_with_signal(self):
        """Тест обработки свечи с сигналом"""
        # Создаем мок свечи
        mock_candle = Mock()
        mock_candle.close = Quotation(units=100, nano=0)
        mock_candle.time = datetime.now()
        
        # Создаем мок сигнала
        mock_signal = Mock()
        mock_signal.trough_detected = True
        mock_signal.peak_detected = False
        mock_signal.histogram = -0.5
        mock_signal.macd = -0.3
        mock_signal.signal = -0.2
        mock_signal.macd_prev = -0.4
        mock_signal.signal_prev = -0.1
        mock_signal.candle = mock_candle
        
        # Мокаем signal_manager, чтобы он возвращал сигнал
        self.mock_signal_manager.add_candle = Mock(return_value=mock_signal)
        
        # Мокаем стратегии, чтобы они возвращали пустые списки заказов
        for strategy in self.strategy_manager._strategies:
            strategy.execute = AsyncMock(return_value=[])
        
        await self.strategy_manager.on_candle(mock_candle)
        
        # Проверяем, что заказы не добавились (стратегии возвращают пустые списки)
        self.assertEqual(len(self.strategy_manager._orders), 0)
    
    def test_candles_property(self):
        """Тест свойства candles"""
        # Мокаем signal_manager.candles
        mock_candles = [{'time': datetime.now(), 'close': 100.0}]
        self.mock_signal_manager.candles = mock_candles
        
        candles = self.strategy_manager.candles
        
        self.assertIsNotNone(candles)
        self.assertEqual(len(candles), 1)
    
    
    def test_print_trades(self):
        """Тест печати заказов"""
        # Создаем тестовые заказы
        test_orders = [
            OrderIntent(
                figi="FUTIMOEXF000",
                direction=OrderDirection.BUY,
                order_type=OrderType.MARKET,
                quantity=1,
                price=100.0
            ),
            OrderIntent(
                figi="FUTIMOEXF000",
                direction=OrderDirection.SELL,
                order_type=OrderType.MARKET,
                quantity=1,
                price=105.0
            )
        ]
        
        # Добавляем заказы в переменную экземпляра
        self.strategy_manager._orders.extend(test_orders)
        
        # Проверяем, что метод не падает
        try:
            self.strategy_manager.print_trades()
        except Exception as e:
            self.fail(f"print_trades() raised {type(e).__name__}: {e}")
    
    def test_trades_property(self):
        """Тест свойства trades"""
        # Создаем тестовые заказы
        test_orders = [
            OrderIntent(
                figi="FUTIMOEXF000",
                direction=OrderDirection.BUY,
                order_type=OrderType.MARKET,
                quantity=1,
                price=100.0
            ),
            OrderIntent(
                figi="FUTIMOEXF000",
                direction=OrderDirection.SELL,
                order_type=OrderType.MARKET,
                quantity=1,
                price=105.0
            )
        ]
        
        # Добавляем заказы в переменную экземпляра
        self.strategy_manager._orders.extend(test_orders)
        
        # Получаем trades
        trades = self.strategy_manager.trades
        
        self.assertIsNotNone(trades)
        self.assertEqual(len(trades), 2)
    
    
    def test_risk_limits_access(self):
        """Тест доступа к лимитам рисков через мок"""
        # Проверяем, что можем получить доступ к настройкам
        self.assertEqual(self.mock_risk_manager.risk_limits.percent_from_deposit, 50.0)
        self.assertEqual(self.mock_risk_manager.risk_limits.items_per_trade, 20)
        self.assertEqual(self.mock_risk_manager.risk_limits.stop_loss_threshold, 8.0)
    
    @pytest.mark.asyncio

    
    async def test_portfolio_manager_access(self):
        """Тест доступа к портфель-менеджеру через мок"""
        # Проверяем, что можем получить депозит
        deposit = await self.mock_portfolio_manager.get_deposit()
        self.assertEqual(deposit, 100000.0)
        
        # Проверяем, что можем получить ГО
        guarantee = await self.mock_portfolio_manager.get_guarantee_deposit("FUTIMOEXF000")
        self.assertEqual(guarantee, 1700.0)
    
    def test_mock_flexibility(self):
        """Тест гибкости моков - можно легко менять параметры"""
        # Создаем новый мок с другими параметрами
        custom_risk_manager = MockRiskManager(
            percent_from_deposit=50.0,
            items_per_trade=5,
            stop_loss_threshold=10.0
        )
        
        # Проверяем, что параметры установились
        self.assertEqual(custom_risk_manager.risk_limits.percent_from_deposit, 50.0)
        self.assertEqual(custom_risk_manager.risk_limits.items_per_trade, 5)
        self.assertEqual(custom_risk_manager.risk_limits.stop_loss_threshold, 10.0)
    
    @pytest.mark.asyncio
    async def test_duplicate_bar_is_skipped(self):
        """Повторная свеча с тем же временем игнорируется (не обрабатывается повторно)."""
        from datetime import datetime
        # Подготовка свечи с фиксированным временем
        fixed_time = datetime(2025, 1, 1, 10, 0, 0)
        mock_candle = Mock()
        mock_candle.time = fixed_time
        # Для совместимости попытки получения цены
        mock_candle.close = Quotation(units=1000, nano=0)

        # Сигнал менеджер возвращает сигналы (чтобы пройти ветку обработки)
        dummy_signal = Mock()
        self.mock_signal_manager.add_candle = Mock(return_value=dummy_signal)

        # Стратегии вернут пустые намерения, но мы считаем вызовы execute
        for strategy in self.strategy_manager._strategies:
            strategy.execute = AsyncMock(return_value=[])

        # Первый вызов — обработка должна пройти
        await self.strategy_manager.on_candle(mock_candle)
        # Второй вызов с тем же временем — должен быть проигнорирован
        await self.strategy_manager.on_candle(mock_candle)

        # add_candle вызван ровно один раз
        self.mock_signal_manager.add_candle.assert_called_once()
        # execute у стратегий вызван по одному разу
        for strategy in self.strategy_manager._strategies:
            assert strategy.execute.call_count == 1

    def tearDown(self):
        """Очистка после тестов"""
        # Очищаем переменную экземпляра _orders после каждого теста
        self.strategy_manager._orders.clear()


# Функция для запуска асинхронных тестов
def async_test(coro):
    """Декоратор для асинхронных тестов"""
    def wrapper(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro(self))
        finally:
            loop.close()
    return wrapper


# Применяем декоратор ко всем асинхронным тестам
for attr_name in dir(TestStrategyManager):
    attr = getattr(TestStrategyManager, attr_name)
    if asyncio.iscoroutinefunction(attr):
        setattr(TestStrategyManager, attr_name, async_test(attr))


if __name__ == '__main__':
    unittest.main()
