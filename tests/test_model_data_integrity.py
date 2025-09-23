#!/usr/bin/env python3
"""
Тесты целостности данных моделей
Проверяют корректность данных в различных моделях системы
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock
from typing import Dict, Any, List

from robotlib.signal_types import Signal
from robotlib.signal_manager import SignalManager
from robotlib.trading.interfaces import TradingDependencies
from robotlib.trading.tinkoff_api_client import TinkoffAPIClient
from robotlib.trading.portfolio_manager import PortfolioManager
from robotlib.trading.risk_manager import RiskManager
from robotlib.trading.order_executor import OrderExecutor
from robotlib.trading.market_data_stream import MarketDataStream
from robotlib.trading.session_stats import SessionStats
from robotlib.strategies.strategy_manager import StrategyManager
from robotlib.utils.money import Money
from robotlib.trading.events import TradingEvent, EventType
from visualization.data_manager import DataManager


class TestModelDataIntegrity:
    """Тесты целостности данных моделей"""
    
    @pytest.fixture
    def mock_config(self):
        """Мок конфигурации"""
        config = Mock()
        config.tcs_client = Mock()
        config.tcs_client.token = "test_token"
        config.tcs_client.account_id = "test_account"
        config.tcs_client.sandbox_token = "test_sandbox_token"
        return config
    
    @pytest.fixture
    def mock_api_client(self):
        """Мок API клиента"""
        api_client = Mock(spec=TinkoffAPIClient)
        api_client.get_candles = AsyncMock(return_value=Mock(candles=[]))
        api_client.get_margin = AsyncMock(return_value=Mock())
        api_client.get_portfolio = AsyncMock(return_value=Mock())
        return api_client
    
    @pytest.fixture
    def test_signal_model_integrity(self):
        """Тест целостности модели Signal"""
        # Создаем тестовую свечу
        mock_candle = Mock()
        mock_candle.time = datetime.now()
        mock_candle.open = Money(1000, 0)
        mock_candle.high = Money(1010, 0)
        mock_candle.low = Money(990, 0)
        mock_candle.close = Money(1005, 0)
        mock_candle.volume = 1000
        
        # Создаем сигнал
        signal = Signal(
            macd=0.5,
            signal=0.3,
            histogram=0.2,
            macd_prev=0.4,
            signal_prev=0.2,
            peak_detected=True,
            trough_detected=False,
            candle=mock_candle
        )
        
        # Проверяем целостность данных
        assert signal.macd == 0.5
        assert signal.signal == 0.3
        assert signal.histogram == 0.2
        assert signal.macd_prev == 0.4
        assert signal.signal_prev == 0.2
        assert signal.peak_detected is True
        assert signal.trough_detected is False
        assert signal.candle == mock_candle
        
        # Проверяем логическую целостность
        assert signal.histogram == signal.macd - signal.signal
        assert isinstance(signal.peak_detected, bool)
        assert isinstance(signal.trough_detected, bool)
        assert not (signal.peak_detected and signal.trough_detected)  # Не могут быть одновременно
    
    def test_money_model_integrity(self):
        """Тест целостности модели Money"""
        # Тестируем различные значения
        test_cases = [
            (1000, 0, 1000.0),
            (1000, 500000000, 1000.5),
            (0, 500000000, 0.5),
            (1000000, 0, 1000000.0),
            (0, 0, 0.0),
        ]
        
        for units, nano, expected_float in test_cases:
            money = Money(units, nano)
            
            # Проверяем целостность
            assert money.units == units
            assert money.nano == nano
            assert money.to_float() == expected_float
            
            # Проверяем обратную конвертацию
            converted_money = Money.from_float(expected_float)
            assert abs(converted_money.units - units) <= 1
            assert abs(converted_money.nano - nano) <= 1
    
    def test_trading_dependencies_integrity(self, mock_api_client):
        """Тест целостности TradingDependencies"""
        # Создаем моки для всех зависимостей
        session_stats = Mock()
        portfolio_manager = Mock()
        risk_manager = Mock()
        order_executor = Mock()
        market_data_stream = Mock()
        signal_manager = Mock()
        strategy_manager = Mock()
        
        # Создаем TradingDependencies
        dependencies = TradingDependencies(
            api_client=mock_api_client,
            session_stats=session_stats,
            portfolio_manager=portfolio_manager,
            risk_manager=risk_manager,
            order_executor=order_executor,
            market_data_stream=market_data_stream,
            signal_manager=signal_manager,
            strategy_manager=strategy_manager
        )
        
        # Проверяем целостность
        assert dependencies.api_client == mock_api_client
        assert dependencies.session_stats == session_stats
        assert dependencies.portfolio_manager == portfolio_manager
        assert dependencies.risk_manager == risk_manager
        assert dependencies.order_executor == order_executor
        assert dependencies.market_data_stream == market_data_stream
        assert dependencies.signal_manager == signal_manager
        assert dependencies.strategy_manager == strategy_manager
        
        # Проверяем, что все атрибуты установлены
        assert hasattr(dependencies, 'api_client')
        assert hasattr(dependencies, 'session_stats')
        assert hasattr(dependencies, 'portfolio_manager')
        assert hasattr(dependencies, 'risk_manager')
        assert hasattr(dependencies, 'order_executor')
        assert hasattr(dependencies, 'market_data_stream')
        assert hasattr(dependencies, 'signal_manager')
        assert hasattr(dependencies, 'strategy_manager')
    
    def test_session_stats_integrity(self):
        """Тест целостности SessionStats"""
        session_stats = SessionStats()
        
        # Добавляем тестовые данные
        session_stats.add_trade(1000.0, 10, 'buy')
        session_stats.add_trade(1010.0, 5, 'sell')
        session_stats.add_trade(1020.0, 3, 'buy')
        
        # Получаем статистику
        stats = session_stats.get_stats()
        
        # Проверяем целостность данных
        assert stats['total_trades'] == 3
        assert stats['buy_trades'] == 2
        assert stats['sell_trades'] == 1
        assert stats['total_volume'] == 18  # 10 + 5 + 3
        assert stats['total_pnl'] == 0.0  # 1000*10 - 1010*5 + 1020*3 = 0
        
        # Проверяем логическую целостность
        assert stats['buy_trades'] + stats['sell_trades'] == stats['total_trades']
        assert stats['total_volume'] > 0
        assert isinstance(stats['total_pnl'], float)
    
    def test_data_manager_integrity(self):
        """Тест целостности DataManager"""
        data_manager = DataManager()
        
        # Добавляем тестовые данные
        candle_data = {
            'time': datetime.now(),
            'open': 1000.0,
            'high': 1010.0,
            'low': 990.0,
            'close': 1005.0,
            'volume': 1000
        }
        data_manager.add_candle(candle_data)
        
        signal_data = {
            'time': datetime.now(),
            'type': 'buy',
            'strength': 0.5,
            'price': 1005.0
        }
        data_manager.add_signal(signal_data)
        
        # Получаем снимок данных
        snapshot = data_manager.get_data_snapshot()
        
        # Проверяем целостность
        assert len(snapshot['candles_data']) == 1
        assert len(snapshot['signals_data']) == 1
        assert snapshot['current_price'] == 1005.0
        assert snapshot['buy_count'] == 1
        assert snapshot['sell_count'] == 0
        
        # Проверяем структуру данных
        assert 'candles_data' in snapshot
        assert 'signals_data' in snapshot
        assert 'portfolio_data' in snapshot
        assert 'current_price' in snapshot
        assert 'last_update' in snapshot
        assert 'buy_count' in snapshot
        assert 'sell_count' in snapshot
        assert 'orders_count' in snapshot
        assert 'total_volume' in snapshot
    
    def test_event_data_integrity(self):
        """Тест целостности данных событий"""
        # Тестируем различные типы событий
        test_events = [
            (EventType.CANDLE_RECEIVED, {'candle': Mock(), 'figi': 'TEST', 'price': 1000.0}),
            (EventType.SIGNAL_GENERATED, {'signal': Mock(), 'figi': 'TEST', 'price': 1000.0}),
            (EventType.ORDER_PLACED, {'order': Mock(), 'figi': 'TEST'}),
            (EventType.ORDER_FILLED, {'order': Mock(), 'figi': 'TEST', 'price': 1000.0}),
            (EventType.POSITION_OPENED, {'position': Mock(), 'figi': 'TEST'}),
            (EventType.POSITION_CLOSED, {'position': Mock(), 'figi': 'TEST', 'pnl': 100.0}),
            (EventType.PORTFOLIO_UPDATED, {'portfolio': Mock()}),
            (EventType.MARKET_STATUS_CHANGED, {'status': 'open', 'session': 'main'})
        ]
        
        for event_type, data in test_events:
            event = TradingEvent(event_type, data)
            
            # Проверяем целостность
            assert event.event_type == event_type
            assert isinstance(event.data, dict)
            assert event.data == data
            
            # Проверяем, что данные соответствуют типу события
            if event_type == EventType.CANDLE_RECEIVED:
                assert 'candle' in event.data
                assert 'figi' in event.data
            elif event_type == EventType.SIGNAL_GENERATED:
                assert 'signal' in event.data
                assert 'figi' in event.data
            elif event_type in [EventType.ORDER_PLACED, EventType.ORDER_FILLED]:
                assert 'order' in event.data
                assert 'figi' in event.data
            elif event_type in [EventType.POSITION_OPENED, EventType.POSITION_CLOSED]:
                assert 'position' in event.data
                assert 'figi' in event.data
            elif event_type == EventType.PORTFOLIO_UPDATED:
                assert 'portfolio' in event.data
            elif event_type == EventType.MARKET_STATUS_CHANGED:
                assert 'status' in event.data
    
    def test_signal_manager_data_integrity(self):
        """Тест целостности данных в SignalManager"""
        signal_manager = SignalManager()
        
        # Создаем серию тестовых свечей
        base_time = datetime.now()
        for i in range(10):
            mock_candle = Mock()
            mock_candle.time = base_time + timedelta(minutes=i)
            price = 1000.0 + i * 0.5
            mock_candle.open = Money(int(price), int((price - int(price)) * 1e9))
            mock_candle.high = Money(int(price + 1), int(((price + 1) - int(price + 1)) * 1e9))
            mock_candle.low = Money(int(price - 1), int(((price - 1) - int(price - 1)) * 1e9))
            mock_candle.close = Money(int(price), int((price - int(price)) * 1e9))
            mock_candle.volume = 1000 + i * 10
            
            signal = signal_manager.add_candle(mock_candle)
            
            if signal:
                # Проверяем целостность сигнала
                assert hasattr(signal, 'macd')
                assert hasattr(signal, 'signal')
                assert hasattr(signal, 'histogram')
                assert hasattr(signal, 'candle')
                
                # Проверяем логическую целостность
                assert signal.histogram == signal.macd - signal.signal
                assert signal.candle == mock_candle
                
                # Проверяем, что значения в разумных пределах
                assert -1000 <= signal.macd <= 1000
                assert -1000 <= signal.signal <= 1000
                assert -1000 <= signal.histogram <= 1000
        
        # Проверяем целостность данных в SignalManager
        candles = signal_manager.candles
        assert len(candles) > 0
        
        # Проверяем, что данные в candles соответствуют добавленным свечам
        for i, candle_data in enumerate(candles):
            assert 'date' in candle_data
            assert 'open' in candle_data
            assert 'high' in candle_data
            assert 'low' in candle_data
            assert 'close' in candle_data
            assert 'macd' in candle_data
            assert 'signal' in candle_data
            assert 'histogram' in candle_data
            
            # Проверяем логическую целостность
            assert candle_data['high'] >= candle_data['low']
            assert candle_data['high'] >= candle_data['open']
            assert candle_data['high'] >= candle_data['close']
            assert candle_data['low'] <= candle_data['open']
            assert candle_data['low'] <= candle_data['close']
    
    def test_portfolio_data_integrity(self, mock_api_client, mock_config):
        """Тест целостности данных портфеля"""
        from robotlib.utils.money import Money
        
        # Создаем мок ответа API
        mock_position = Mock()
        mock_position.figi = 'TEST_FIGI'
        mock_position.instrument_type = 'futures'
        mock_position.quantity = Money(100)
        mock_position.average_position_price = Money(1000)
        mock_position.current_price = Money(1005)
        mock_position.expected_yield = Money(100)
        
        mock_response = Mock()
        mock_response.total_amount_currencies = [Money(100000)]
        mock_response.total_amount_portfolio = Money(100000)
        mock_response.positions = [mock_position]
        
        mock_api_client.get_portfolio.return_value = mock_response
        
        # Создаем PortfolioManager
        portfolio_manager = PortfolioManager(mock_api_client)
        
        # Получаем данные портфеля
        portfolio_data = asyncio.run(portfolio_manager.get_portfolio_data())
        
        # Проверяем целостность данных
        assert portfolio_data is not None
        assert 'total_amount' in portfolio_data
        assert 'positions' in portfolio_data
        assert 'last_update' in portfolio_data
        
        assert portfolio_data['total_amount'] == 100000.0
        assert len(portfolio_data['positions']) == 1
        
        position = portfolio_data['positions'][0]
        assert position['figi'] == 'TEST_FIGI'
        assert position['quantity'] == 100
        assert position['average_price'] == 1000.0
        assert position['current_price'] == 1005.0
        assert position['unrealized_pnl'] == 500.0  # (1005 - 1000) * 100
        
        # Проверяем логическую целостность
        assert portfolio_data['total_amount'] > 0
        assert all(pos['quantity'] > 0 for pos in portfolio_data['positions'])
        assert all(pos['average_price'] > 0 for pos in portfolio_data['positions'])
    
    def test_risk_limits_integrity(self):
        """Тест целостности лимитов риска"""
        from robotlib.trading.risk_manager import RiskLimits
        
        # Создаем лимиты риска
        risk_limits = RiskLimits(
            max_position_size=1000.0,
            max_daily_loss=500.0,
            percent_from_deposit=50.0,
            items_per_trade=20,
            stop_loss_threshold=8.0
        )
        
        # Проверяем целостность
        assert risk_limits.max_position_size == 1000.0
        assert risk_limits.max_daily_loss == 500.0
        assert risk_limits.percent_from_deposit == 50.0
        assert risk_limits.items_per_trade == 20
        assert risk_limits.stop_loss_threshold == 8.0
        
        # Проверяем логическую целостность
        assert risk_limits.max_position_size > 0
        assert risk_limits.max_daily_loss > 0
        assert 0 < risk_limits.percent_from_deposit <= 100
        assert risk_limits.items_per_trade > 0
        assert risk_limits.stop_loss_threshold > 0
        assert risk_limits.max_daily_loss < risk_limits.max_position_size
    
    def test_cross_component_data_consistency(self):
        """Тест консистентности данных между компонентами"""
        # Создаем компоненты
        signal_manager = SignalManager()
        data_manager = DataManager()
        
        # Создаем тестовую свечу
        mock_candle = Mock()
        mock_candle.time = datetime.now()
        mock_candle.open = Money(1000, 0)
        mock_candle.high = Money(1010, 0)
        mock_candle.low = Money(990, 0)
        mock_candle.close = Money(1005, 0)
        mock_candle.volume = 1000
        
        # Обрабатываем свечу в SignalManager
        signal = signal_manager.add_candle(mock_candle)
        
        # Обрабатываем свечу в DataManager
        candle_data = {
            'time': mock_candle.time,
            'open': Money(mock_candle.open).to_float(),
            'high': Money(mock_candle.high).to_float(),
            'low': Money(mock_candle.low).to_float(),
            'close': Money(mock_candle.close).to_float(),
            'volume': mock_candle.volume
        }
        data_manager.add_candle(candle_data)
        
        # Проверяем консистентность данных
        signal_candle = signal.candle if signal else None
        data_snapshot = data_manager.get_data_snapshot()
        data_candle = data_snapshot['candles_data'][0] if data_snapshot['candles_data'] else None
        
        if signal_candle and data_candle:
            assert Money(signal_candle.open).to_float() == data_candle['open']
            assert Money(signal_candle.high).to_float() == data_candle['high']
            assert Money(signal_candle.low).to_float() == data_candle['low']
            assert Money(signal_candle.close).to_float() == data_candle['close']
            assert signal_candle.volume == data_candle['volume']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

