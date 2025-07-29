#!/usr/bin/env python3
"""
Модуль для управления TradingSession
Управляет инициализацией и работой с TradingSession
"""

import asyncio
import random
import traceback
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from talipp.indicators import MACD, ATR

from robotlib.trading.trading_session import TradingConfig
from .interfaces import DependenciesProvidable
from robotlib.utils.logger import get_logger
from robotlib.trading.risk_manager import RiskLimits


class TradingSessionManager:
    """Менеджер TradingSession для визуализации"""
    
    def __init__(self, 
                 trading_session: Any,
                 signal_manager: Any = None,
                 strategy_params: Dict[str, Any] = None):
        """
        Инициализация TradingSessionManager
        
        Args:
            trading_session: Готовая торговая сессия (обязательно)
            signal_manager: Менеджер сигналов (опционально)
            strategy_params: Параметры стратегии
        """
        self.trading_session = trading_session
        self.signal_manager = signal_manager
        self.strategy_params = strategy_params or {}
        self.logger = get_logger("trading_session_manager")
        
        # Инициализация
        self._initialize_strategy_manager()
    
    
    def _initialize_strategy_manager(self) -> None:
        """Инициализирует StrategyManager для визуализации"""
        try:
            if not self.trading_session:
                raise RuntimeError("TradingSession не инициализирован")
            
            # Получаем SignalManager из TradingSession
            if hasattr(self.trading_session, 'signal_manager') and self.trading_session.signal_manager:
                self.signal_manager = self.trading_session.signal_manager
                self.logger.info("SignalManager получен из TradingSession")
            else:
                self.logger.warning("SignalManager не найден в TradingSession")
            
        except Exception as e:
            self.logger.error(f"Ошибка инициализации StrategyManager: {e}")
            self.logger.error(f"Трассировка: {traceback.format_exc()}")
            raise RuntimeError(f"Не удалось инициализировать StrategyManager: {e}") from e
    
    
    async def get_trading_session_signals(self, candle) -> List[Dict[str, Any]]:
        """Получает сигналы от TradingSession"""
        try:
            self.logger.info(f"🔍 Проверяем сигналы для свечи: {candle.close:.2f} ₽")
            
            # Проверяем доступность компонентов
            if not self.trading_session:
                self.logger.warning("❌ TradingSession не инициализирован")
                return []
                
            if not self.trading_session.strategy_manager:
                self.logger.warning("❌ StrategyManager не инициализирован")
                return []
                
            if not hasattr(self.trading_session.strategy_manager, '_strategies'):
                self.logger.warning("❌ Стратегии не инициализированы")
                return []
                
            self.logger.info(f"📊 Доступно стратегий: {len(self.trading_session.strategy_manager._strategies)}")
            
            # Создаем объект свечи для TradingSession
            class ProcessedCandle:
                def __init__(self, candle_data):
                    self.time = candle_data['time']
                    self.open = candle_data['open']
                    self.high = candle_data['high']
                    self.low = candle_data['low']
                    self.close = candle_data['close']
                    self.volume = candle_data['volume']
            
            processed_candle = ProcessedCandle({
                'time': candle.time,
                'open': candle.open,
                'high': candle.high,
                'low': candle.low,
                'close': candle.close,
                'volume': candle.volume
            })
            
            # Проверяем SignalManager
            if hasattr(self.trading_session.strategy_manager, '_signal_manager'):
                signal_manager = self.trading_session.strategy_manager._signal_manager
                self.logger.info(f"📈 SignalManager: {len(signal_manager.candles)} свечей, MACD: {len(signal_manager._macd) if hasattr(signal_manager, '_macd') else 0}")
                
                # Проверяем последний сигнал
                if hasattr(signal_manager, '_macd') and len(signal_manager._macd) > 0:
                    last_macd = signal_manager._macd[-1]
                    self.logger.info(f"📊 Последний MACD: {last_macd.macd:.4f}, Signal: {last_macd.signal:.4f}, Histogram: {last_macd.histogram:.4f}")
                    
                    # Проверяем условия для генерации сигналов
                    if len(signal_manager._macd) > 1:
                        prev_macd = signal_manager._macd[-2]
                        self.logger.info(f"📊 Предыдущий MACD: {prev_macd.macd:.4f}, Signal: {prev_macd.signal:.4f}")
                        
                        # Проверяем пересечения
                        macd_crossed_up = prev_macd.macd < prev_macd.signal and last_macd.macd > last_macd.signal
                        macd_crossed_down = prev_macd.macd > prev_macd.signal and last_macd.macd < last_macd.signal
                        
                        self.logger.info(f"🔄 MACD пересечения: вверх={macd_crossed_up}, вниз={macd_crossed_down}")
                        
                        # Проверяем пики и впадины
                        if hasattr(signal_manager, '_hist_window') and len(signal_manager._hist_window) > 0:
                            hist_abs = abs(last_macd.histogram)
                            self.logger.info(f"📊 Абсолютное значение гистограммы: {hist_abs:.4f} (порог: 0.1)")
            
            # Получаем приказы от стратегий через TradingSession
            orders = await self.trading_session.strategy_manager.on_candle(processed_candle)
            
            self.logger.info(f"📊 Получено приказов от стратегий: {len(orders) if orders else 0}")
            
            signals = []
            if orders:
                for order in orders:
                    signal_data = {
                        'time': candle.time,
                        'price': candle.close,
                        'type': 'buy' if order.type in ['buy', 'long_buy'] else 'sell',
                        'reason': f'TradingSession: {order.type}',
                        'quantity': order.quantity,
                        'strategy': order.strategy_name if hasattr(order, 'strategy_name') else 'Unknown'
                    }
                    signals.append(signal_data)
                    
                    if signal_data['type'] == 'buy':
                        self.logger.info(f"🟢 Сигнал ПОКУПКИ от TradingSession: {candle.close:.2f} ₽ (qty: {order.quantity})")
                    else:
                        self.logger.info(f"🔴 Сигнал ПРОДАЖИ от TradingSession: {candle.close:.2f} ₽ (qty: {order.quantity})")
            else:
                self.logger.info("ℹ️ Нет приказов от стратегий")
                
                # Дополнительная диагностика стратегий
                for i, strategy in enumerate(self.trading_session.strategy_manager._strategies):
                    strategy_name = strategy.__class__.__name__
                    position = getattr(strategy, '_position', 0)
                    wait_buy = getattr(strategy, '_wait_buy_cross', False)
                    wait_sell = getattr(strategy, '_wait_sell_cross', False)
                    wait_short_sell = getattr(strategy, '_wait_short_sell_cross', False)
                    wait_short_buy = getattr(strategy, '_wait_short_buy_cross', False)
                    
                    self.logger.info(f"📋 {strategy_name}: позиция={position}, wait_buy={wait_buy}, wait_sell={wait_sell}, wait_short_sell={wait_short_sell}, wait_short_buy={wait_short_buy}")
            
            return signals
                
        except Exception as e:
            self.logger.error(f"Ошибка получения сигналов от TradingSession: {e}")
            self.logger.error(f"Трассировка: {traceback.format_exc()}")
            return []
    
    def update_orders_from_trading_session(self) -> List[Dict[str, Any]]:
        """Обновляет данные об ордерах из TradingSession"""
        try:
            if not self.trading_session or not self.trading_session.strategy_manager:
                return []
            
            # Получаем ордера из StrategyManager
            if hasattr(self.trading_session.strategy_manager, 'trades'):
                trades_df = self.trading_session.strategy_manager.trades
                
                if not trades_df.empty:
                    # Конвертируем DataFrame в список словарей для визуализации
                    orders_data = []
                    for _, trade in trades_df.iterrows():
                        order_data = {
                            'time': trade['date'],
                            'price': trade['marker_price'],
                            'type': trade['type'],
                            'quantity': trade.get('quantity', 1),
                            'strategy': trade.get('strategy_name', 'Unknown'),
                            'reason': f"Order: {trade['type']}"
                        }
                        orders_data.append(order_data)
                    
                    self.logger.info(f"📊 Обновлено {len(orders_data)} ордеров из TradingSession")
                    return orders_data
            
            return []
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления ордеров: {e}")
            return []
    
    def get_strategy_status(self) -> List[Dict[str, Any]]:
        """Получает статус стратегий"""
        try:
            if not self.trading_session or not self.trading_session.strategy_manager:
                return []
            
            strategy_status = []
            
            if hasattr(self.trading_session.strategy_manager, '_strategies'):
                for strategy in self.trading_session.strategy_manager._strategies:
                    strategy_name = strategy.__class__.__name__
                    
                    # Получаем информацию о стратегии
                    income = getattr(strategy, 'income', 0)
                    position = getattr(strategy, 'position', 0)
                    
                    strategy_status.append({
                        'name': strategy_name,
                        'income': income,
                        'position': position
                    })
            
            return strategy_status
            
        except Exception as e:
            self.logger.error(f"Ошибка получения статуса стратегий: {e}")
            return []
    
    def reset_strategies(self) -> None:
        """Сбрасывает состояние стратегий"""
        try:
            if self.trading_session and self.trading_session.strategy_manager:
                for strategy in self.trading_session.strategy_manager.strategies.values():
                    strategy._position = 0
                    strategy._income = 0.0
                    strategy._wait_buy_cross = True
                    strategy._wait_sell_cross = True
                    strategy._wait_short_sell = True
                    strategy._wait_short_buy = True
            
            # Сбрасываем SignalManager
            if self.signal_manager:
                self.signal_manager.candles.clear()
                self.signal_manager._macd = MACD(fast_period=6, slow_period=11, signal_period=9)
                self.signal_manager._atr = ATR(period=7)
                self.signal_manager._hist_window.clear()
            
            self.logger.info("Стратегии сброшены")
            
        except Exception as e:
            self.logger.error(f"Ошибка сброса стратегий: {e}")
    
    def preload_strategy_data(self, candles_data: List[Dict[str, Any]]) -> None:
        """Предварительная подгрузка данных для стратегий"""
        try:
            if not self.trading_session or not self.trading_session.strategy_manager:
                self.logger.warning("TradingSession недоступен для предварительной подгрузки")
                return
            
            self.logger.info("🔥 Начинаем предварительную подгрузку данных для стратегий...")
            
            # Проверяем SignalManager
            signal_manager = self.trading_session.strategy_manager._signal_manager
            self.logger.info(f"📈 SignalManager до подгрузки: {len(signal_manager.candles)} свечей")
            
            # Создаем объект свечи для TradingSession
            class ProcessedCandle:
                def __init__(self, candle_data):
                    self.time = candle_data['time']
                    self.open = candle_data['open']
                    self.high = candle_data['high']
                    self.low = candle_data['low']
                    self.close = candle_data['close']
                    self.volume = candle_data['volume']
            
            # ПРИНУДИТЕЛЬНО генерируем достаточно данных для MACD (минимум 20 свечей)
            if len(candles_data) < 20:
                self.logger.info("📊 Генерируем дополнительные данные для MACD...")
                base_time = datetime.now() - timedelta(hours=1)
                base_price = candles_data[-1]['close'] if candles_data else 2923.50
                
                for i in range(20 - len(candles_data)):
                    price_change = random.uniform(-5, 5)  # Небольшие случайные изменения
                    new_price = base_price + price_change
                    
                    candle_data = {
                        'time': base_time + timedelta(minutes=i),
                        'open': base_price,
                        'high': max(base_price, new_price) + random.uniform(0, 2),
                        'low': min(base_price, new_price) - random.uniform(0, 2),
                        'close': new_price,
                        'volume': random.randint(1000, 5000)
                    }
                    
                    # Добавляем в SignalManager
                    processed_candle = ProcessedCandle(candle_data)
                    signal_manager.add_candle(processed_candle)
                    
                    base_price = new_price
                
                self.logger.info(f"✅ Сгенерировано {20 - len(candles_data)} дополнительных свечей")
            
            # Подгружаем все исторические свечи в стратегии
            processed_count = 0
            signals_generated = 0
            
            for candle_data in candles_data:
                processed_candle = ProcessedCandle(candle_data)
                
                # Добавляем свечу в StrategyManager для разогрева стратегий
                orders = asyncio.run(self.trading_session.strategy_manager.on_candle(processed_candle))
                processed_count += 1
                
                if orders:
                    signals_generated += len(orders)
                    self.logger.info(f"🎯 Сгенерирован сигнал на свече {processed_count}: {len(orders)} приказов")
                
                # Логируем прогресс каждые 100 свечей
                if processed_count % 100 == 0:
                    self.logger.info(f"📊 Обработано {processed_count}/{len(candles_data)} свечей для стратегий, сигналов: {signals_generated}")
            
            self.logger.info(f"✅ Предварительная подгрузка завершена! Обработано {processed_count} свечей, сгенерировано {signals_generated} сигналов")
            self.logger.info("🚀 Стратегии готовы к работе с полной историей данных")
            
        except Exception as e:
            self.logger.error(f"Ошибка предварительной подгрузки данных для стратегий: {e}")
            self.logger.error(f"Трассировка: {traceback.format_exc()}")
