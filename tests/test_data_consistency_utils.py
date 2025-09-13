#!/usr/bin/env python3
"""
Утилиты для тестирования консистентности данных
Вспомогательные функции и классы для проверки целостности данных
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from robotlib.trading.event_bus_interface import EventBus, TradingEvent, EventType
from robotlib.signal_manager import SignalManager, Signal
from robotlib.utils.money import Money
from visualization.data_manager import DataManager


class DataConsistencyLevel(Enum):
    """Уровни консистентности данных"""
    BASIC = "basic"           # Базовая проверка
    STRUCTURAL = "structural" # Структурная проверка
    LOGICAL = "logical"       # Логическая проверка
    TEMPORAL = "temporal"     # Временная проверка
    COMPLETE = "complete"     # Полная проверка


@dataclass
class ConsistencyCheckResult:
    """Результат проверки консистентности"""
    is_consistent: bool
    level: DataConsistencyLevel
    errors: List[str]
    warnings: List[str]
    details: Dict[str, Any]


class DataConsistencyChecker:
    """Проверяет консистентность данных в системе"""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.check_results: List[ConsistencyCheckResult] = []
    
    def check_candle_data_consistency(self, candle_data: Dict[str, Any], 
                                    level: DataConsistencyLevel = DataConsistencyLevel.BASIC) -> ConsistencyCheckResult:
        """Проверяет консистентность данных свечи"""
        errors = []
        warnings = []
        details = {}
        
        # Базовая проверка
        if level in [DataConsistencyLevel.BASIC, DataConsistencyLevel.STRUCTURAL, 
                    DataConsistencyLevel.LOGICAL, DataConsistencyLevel.TEMPORAL, DataConsistencyLevel.COMPLETE]:
            
            # Проверяем наличие обязательных полей
            required_fields = ['time', 'open', 'high', 'low', 'close', 'volume']
            for field in required_fields:
                if field not in candle_data:
                    errors.append(f"Missing required field: {field}")
            
            # Проверяем типы данных
            if 'time' in candle_data and not isinstance(candle_data['time'], datetime):
                errors.append("Field 'time' must be datetime")
            
            for field in ['open', 'high', 'low', 'close', 'volume']:
                if field in candle_data and not isinstance(candle_data[field], (int, float)):
                    errors.append(f"Field '{field}' must be numeric")
        
        # Структурная проверка
        if level in [DataConsistencyLevel.STRUCTURAL, DataConsistencyLevel.LOGICAL, 
                    DataConsistencyLevel.TEMPORAL, DataConsistencyLevel.COMPLETE]:
            
            # Проверяем, что high >= low
            if 'high' in candle_data and 'low' in candle_data:
                if candle_data['high'] < candle_data['low']:
                    errors.append("High price cannot be less than low price")
            
            # Проверяем, что high >= open и high >= close
            if 'high' in candle_data:
                if 'open' in candle_data and candle_data['high'] < candle_data['open']:
                    errors.append("High price cannot be less than open price")
                if 'close' in candle_data and candle_data['high'] < candle_data['close']:
                    errors.append("High price cannot be less than close price")
            
            # Проверяем, что low <= open и low <= close
            if 'low' in candle_data:
                if 'open' in candle_data and candle_data['low'] > candle_data['open']:
                    errors.append("Low price cannot be greater than open price")
                if 'close' in candle_data and candle_data['low'] > candle_data['close']:
                    errors.append("Low price cannot be greater than close price")
        
        # Логическая проверка
        if level in [DataConsistencyLevel.LOGICAL, DataConsistencyLevel.TEMPORAL, DataConsistencyLevel.COMPLETE]:
            
            # Проверяем, что цены положительные
            for field in ['open', 'high', 'low', 'close']:
                if field in candle_data and candle_data[field] <= 0:
                    errors.append(f"Price field '{field}' must be positive")
            
            # Проверяем, что объем положительный
            if 'volume' in candle_data and candle_data['volume'] < 0:
                errors.append("Volume must be non-negative")
        
        # Временная проверка
        if level in [DataConsistencyLevel.TEMPORAL, DataConsistencyLevel.COMPLETE]:
            
            # Проверяем, что время не в будущем
            if 'time' in candle_data:
                if candle_data['time'] > datetime.now():
                    warnings.append("Candle time is in the future")
                
                # Проверяем, что время не слишком далеко в прошлом
                if candle_data['time'] < datetime.now() - timedelta(days=365):
                    warnings.append("Candle time is more than a year ago")
        
        # Полная проверка
        if level == DataConsistencyLevel.COMPLETE:
            
            # Проверяем разумность цен
            if all(field in candle_data for field in ['open', 'high', 'low', 'close']):
                price_range = candle_data['high'] - candle_data['low']
                if price_range > candle_data['close'] * 0.1:  # Более 10% от цены закрытия
                    warnings.append("Price range seems unusually large")
        
        details['checked_fields'] = list(candle_data.keys())
        details['price_range'] = candle_data.get('high', 0) - candle_data.get('low', 0) if 'high' in candle_data and 'low' in candle_data else 0
        
        return ConsistencyCheckResult(
            is_consistent=len(errors) == 0,
            level=level,
            errors=errors,
            warnings=warnings,
            details=details
        )
    
    def check_signal_data_consistency(self, signal_data: Dict[str, Any], 
                                    level: DataConsistencyLevel = DataConsistencyLevel.BASIC) -> ConsistencyCheckResult:
        """Проверяет консистентность данных сигнала"""
        errors = []
        warnings = []
        details = {}
        
        # Базовая проверка
        if level in [DataConsistencyLevel.BASIC, DataConsistencyLevel.STRUCTURAL, 
                    DataConsistencyLevel.LOGICAL, DataConsistencyLevel.TEMPORAL, DataConsistencyLevel.COMPLETE]:
            
            # Проверяем наличие обязательных полей
            required_fields = ['time', 'type', 'strength', 'price']
            for field in required_fields:
                if field not in signal_data:
                    errors.append(f"Missing required field: {field}")
            
            # Проверяем типы данных
            if 'time' in signal_data and not isinstance(signal_data['time'], datetime):
                errors.append("Field 'time' must be datetime")
            
            if 'type' in signal_data and signal_data['type'] not in ['buy', 'sell']:
                errors.append("Field 'type' must be 'buy' or 'sell'")
            
            if 'strength' in signal_data and not isinstance(signal_data['strength'], (int, float)):
                errors.append("Field 'strength' must be numeric")
            
            if 'price' in signal_data and not isinstance(signal_data['price'], (int, float)):
                errors.append("Field 'price' must be numeric")
        
        # Структурная проверка
        if level in [DataConsistencyLevel.STRUCTURAL, DataConsistencyLevel.LOGICAL, 
                    DataConsistencyLevel.TEMPORAL, DataConsistencyLevel.COMPLETE]:
            
            # Проверяем, что сила сигнала в разумных пределах
            if 'strength' in signal_data:
                if signal_data['strength'] < 0:
                    errors.append("Signal strength cannot be negative")
                elif signal_data['strength'] > 10:
                    warnings.append("Signal strength seems unusually high")
        
        # Логическая проверка
        if level in [DataConsistencyLevel.LOGICAL, DataConsistencyLevel.TEMPORAL, DataConsistencyLevel.COMPLETE]:
            
            # Проверяем, что цена положительная
            if 'price' in signal_data and signal_data['price'] <= 0:
                errors.append("Signal price must be positive")
            
            # Проверяем, что сила сигнала положительная
            if 'strength' in signal_data and signal_data['strength'] < 0:
                errors.append("Signal strength must be non-negative")
        
        # Временная проверка
        if level in [DataConsistencyLevel.TEMPORAL, DataConsistencyLevel.COMPLETE]:
            
            # Проверяем, что время не в будущем
            if 'time' in signal_data:
                if signal_data['time'] > datetime.now():
                    warnings.append("Signal time is in the future")
        
        # Полная проверка
        if level == DataConsistencyLevel.COMPLETE:
            
            # Проверяем консистентность MACD данных
            if all(field in signal_data for field in ['macd', 'signal', 'histogram']):
                expected_histogram = signal_data['macd'] - signal_data['signal']
                actual_histogram = signal_data['histogram']
                if abs(expected_histogram - actual_histogram) > 1e-9:
                    errors.append("Histogram does not match MACD - signal calculation")
        
        details['checked_fields'] = list(signal_data.keys())
        details['signal_type'] = signal_data.get('type', 'unknown')
        details['strength'] = signal_data.get('strength', 0)
        
        return ConsistencyCheckResult(
            is_consistent=len(errors) == 0,
            level=level,
            errors=errors,
            warnings=warnings,
            details=details
        )
    
    def check_event_data_consistency(self, event: TradingEvent, 
                                   level: DataConsistencyLevel = DataConsistencyLevel.BASIC) -> ConsistencyCheckResult:
        """Проверяет консистентность данных события"""
        errors = []
        warnings = []
        details = {}
        
        # Базовая проверка
        if level in [DataConsistencyLevel.BASIC, DataConsistencyLevel.STRUCTURAL, 
                    DataConsistencyLevel.LOGICAL, DataConsistencyLevel.TEMPORAL, DataConsistencyLevel.COMPLETE]:
            
            # Проверяем наличие обязательных полей
            if not hasattr(event, 'event_type'):
                errors.append("Event must have event_type")
            
            if not hasattr(event, 'data'):
                errors.append("Event must have data")
            
            # Проверяем типы данных
            if hasattr(event, 'event_type') and not isinstance(event.event_type, EventType):
                errors.append("Event event_type must be EventType enum")
            
            if hasattr(event, 'data') and not isinstance(event.data, dict):
                errors.append("Event data must be dictionary")
        
        # Структурная проверка
        if level in [DataConsistencyLevel.STRUCTURAL, DataConsistencyLevel.LOGICAL, 
                    DataConsistencyLevel.TEMPORAL, DataConsistencyLevel.COMPLETE]:
            
            # Проверяем, что данные соответствуют типу события
            if hasattr(event, 'event_type') and hasattr(event, 'data'):
                if event.event_type == EventType.CANDLE_RECEIVED:
                    if 'candle' not in event.data:
                        errors.append("CANDLE_RECEIVED event must have 'candle' in data")
                    if 'figi' not in event.data:
                        errors.append("CANDLE_RECEIVED event must have 'figi' in data")
                
                elif event.event_type == EventType.SIGNAL_GENERATED:
                    if 'signal' not in event.data:
                        errors.append("SIGNAL_GENERATED event must have 'signal' in data")
                    if 'figi' not in event.data:
                        errors.append("SIGNAL_GENERATED event must have 'figi' in data")
        
        # Логическая проверка
        if level in [DataConsistencyLevel.LOGICAL, DataConsistencyLevel.TEMPORAL, DataConsistencyLevel.COMPLETE]:
            
            # Проверяем, что данные не пустые
            if hasattr(event, 'data') and not event.data:
                warnings.append("Event data is empty")
        
        # Временная проверка
        if level in [DataConsistencyLevel.TEMPORAL, DataConsistencyLevel.COMPLETE]:
            
            # Проверяем, что событие не слишком старое
            if hasattr(event, 'timestamp'):
                if event.timestamp < datetime.now() - timedelta(hours=1):
                    warnings.append("Event is more than an hour old")
        
        details['event_type'] = str(event.event_type) if hasattr(event, 'event_type') else 'unknown'
        details['data_keys'] = list(event.data.keys()) if hasattr(event, 'data') else []
        
        return ConsistencyCheckResult(
            is_consistent=len(errors) == 0,
            level=level,
            errors=errors,
            warnings=warnings,
            details=details
        )
    
    def check_money_consistency(self, money: Money, 
                              level: DataConsistencyLevel = DataConsistencyLevel.BASIC) -> ConsistencyCheckResult:
        """Проверяет консистентность данных Money"""
        errors = []
        warnings = []
        details = {}
        
        # Базовая проверка
        if level in [DataConsistencyLevel.BASIC, DataConsistencyLevel.STRUCTURAL, 
                    DataConsistencyLevel.LOGICAL, DataConsistencyLevel.TEMPORAL, DataConsistencyLevel.COMPLETE]:
            
            # Проверяем наличие обязательных полей
            if not hasattr(money, 'units'):
                errors.append("Money must have units")
            
            if not hasattr(money, 'nano'):
                errors.append("Money must have nano")
            
            # Проверяем типы данных
            if hasattr(money, 'units') and not isinstance(money.units, int):
                errors.append("Money units must be integer")
            
            if hasattr(money, 'nano') and not isinstance(money.nano, int):
                errors.append("Money nano must be integer")
        
        # Структурная проверка
        if level in [DataConsistencyLevel.STRUCTURAL, DataConsistencyLevel.LOGICAL, 
                    DataConsistencyLevel.TEMPORAL, DataConsistencyLevel.COMPLETE]:
            
            # Проверяем, что nano в правильном диапазоне
            if hasattr(money, 'nano'):
                if money.nano < 0:
                    errors.append("Money nano cannot be negative")
                elif money.nano >= 1e9:
                    errors.append("Money nano must be less than 1e9")
        
        # Логическая проверка
        if level in [DataConsistencyLevel.LOGICAL, DataConsistencyLevel.TEMPORAL, DataConsistencyLevel.COMPLETE]:
            
            # Проверяем, что units не отрицательные
            if hasattr(money, 'units') and money.units < 0:
                errors.append("Money units cannot be negative")
            
            # Проверяем консистентность конвертации
            try:
                float_value = money.to_float()
                if float_value < 0:
                    errors.append("Money float value cannot be negative")
            except Exception as e:
                errors.append(f"Money conversion error: {e}")
        
        # Временная проверка
        if level in [DataConsistencyLevel.TEMPORAL, DataConsistencyLevel.COMPLETE]:
            
            # Проверяем, что значения не слишком большие
            if hasattr(money, 'units') and money.units > 1e12:
                warnings.append("Money units seem unusually large")
        
        # Полная проверка
        if level == DataConsistencyLevel.COMPLETE:
            
            # Проверяем обратную конвертацию
            try:
                float_value = money.to_float()
                converted_money = Money.from_float(float_value)
                if abs(converted_money.units - money.units) > 1:
                    warnings.append("Money conversion may have precision loss")
                if abs(converted_money.nano - money.nano) > 1:
                    warnings.append("Money nano conversion may have precision loss")
            except Exception as e:
                errors.append(f"Money reverse conversion error: {e}")
        
        details['units'] = money.units if hasattr(money, 'units') else 0
        details['nano'] = money.nano if hasattr(money, 'nano') else 0
        details['float_value'] = money.to_float() if hasattr(money, 'to_float') else 0
        
        return ConsistencyCheckResult(
            is_consistent=len(errors) == 0,
            level=level,
            errors=errors,
            warnings=warnings,
            details=details
        )
    
    def check_data_manager_consistency(self, data_manager: DataManager, 
                                     level: DataConsistencyLevel = DataConsistencyLevel.BASIC) -> ConsistencyCheckResult:
        """Проверяет консистентность DataManager"""
        errors = []
        warnings = []
        details = {}
        
        try:
            snapshot = data_manager.get_data_snapshot()
        except Exception as e:
            errors.append(f"Failed to get data snapshot: {e}")
            return ConsistencyCheckResult(
                is_consistent=False,
                level=level,
                errors=errors,
                warnings=warnings,
                details=details
            )
        
        # Базовая проверка
        if level in [DataConsistencyLevel.BASIC, DataConsistencyLevel.STRUCTURAL, 
                    DataConsistencyLevel.LOGICAL, DataConsistencyLevel.TEMPORAL, DataConsistencyLevel.COMPLETE]:
            
            # Проверяем наличие обязательных полей
            required_fields = ['candles_data', 'signals_data', 'current_price', 'last_update']
            for field in required_fields:
                if field not in snapshot:
                    errors.append(f"Missing required field in snapshot: {field}")
        
        # Структурная проверка
        if level in [DataConsistencyLevel.STRUCTURAL, DataConsistencyLevel.LOGICAL, 
                    DataConsistencyLevel.TEMPORAL, DataConsistencyLevel.COMPLETE]:
            
            # Проверяем типы данных
            if 'candles_data' in snapshot and not isinstance(snapshot['candles_data'], list):
                errors.append("candles_data must be list")
            
            if 'signals_data' in snapshot and not isinstance(snapshot['signals_data'], list):
                errors.append("signals_data must be list")
            
            if 'current_price' in snapshot and not isinstance(snapshot['current_price'], (int, float)):
                errors.append("current_price must be numeric")
        
        # Логическая проверка
        if level in [DataConsistencyLevel.LOGICAL, DataConsistencyLevel.TEMPORAL, DataConsistencyLevel.COMPLETE]:
            
            # Проверяем, что current_price положительная
            if 'current_price' in snapshot and snapshot['current_price'] <= 0:
                errors.append("current_price must be positive")
            
            # Проверяем консистентность счетчиков
            if all(field in snapshot for field in ['buy_count', 'sell_count', 'total_volume']):
                if snapshot['buy_count'] < 0:
                    errors.append("buy_count cannot be negative")
                if snapshot['sell_count'] < 0:
                    errors.append("sell_count cannot be negative")
                if snapshot['total_volume'] < 0:
                    errors.append("total_volume cannot be negative")
        
        # Временная проверка
        if level in [DataConsistencyLevel.TEMPORAL, DataConsistencyLevel.COMPLETE]:
            
            # Проверяем, что last_update не в будущем
            if 'last_update' in snapshot:
                if snapshot['last_update'] > datetime.now():
                    warnings.append("last_update is in the future")
        
        # Полная проверка
        if level == DataConsistencyLevel.COMPLETE:
            
            # Проверяем консистентность данных свечей
            if 'candles_data' in snapshot:
                for i, candle in enumerate(snapshot['candles_data']):
                    candle_result = self.check_candle_data_consistency(candle, DataConsistencyLevel.BASIC)
                    if not candle_result.is_consistent:
                        errors.append(f"Candle {i} consistency error: {candle_result.errors}")
            
            # Проверяем консистентность данных сигналов
            if 'signals_data' in snapshot:
                for i, signal in enumerate(snapshot['signals_data']):
                    signal_result = self.check_signal_data_consistency(signal, DataConsistencyLevel.BASIC)
                    if not signal_result.is_consistent:
                        errors.append(f"Signal {i} consistency error: {signal_result.errors}")
        
        details['candles_count'] = len(snapshot.get('candles_data', []))
        details['signals_count'] = len(snapshot.get('signals_data', []))
        details['current_price'] = snapshot.get('current_price', 0)
        details['last_update'] = snapshot.get('last_update', None)
        
        return ConsistencyCheckResult(
            is_consistent=len(errors) == 0,
            level=level,
            errors=errors,
            warnings=warnings,
            details=details
        )
    
    def run_comprehensive_check(self, data_manager: DataManager) -> List[ConsistencyCheckResult]:
        """Запускает комплексную проверку консистентности данных"""
        results = []
        
        # Проверяем DataManager
        dm_result = self.check_data_manager_consistency(data_manager, DataConsistencyLevel.COMPLETE)
        results.append(dm_result)
        
        # Проверяем данные свечей
        snapshot = data_manager.get_data_snapshot()
        for i, candle in enumerate(snapshot.get('candles_data', [])):
            candle_result = self.check_candle_data_consistency(candle, DataConsistencyLevel.COMPLETE)
            candle_result.details['candle_index'] = i
            results.append(candle_result)
        
        # Проверяем данные сигналов
        for i, signal in enumerate(snapshot.get('signals_data', [])):
            signal_result = self.check_signal_data_consistency(signal, DataConsistencyLevel.COMPLETE)
            signal_result.details['signal_index'] = i
            results.append(signal_result)
        
        self.check_results.extend(results)
        return results
    
    def get_summary_report(self) -> Dict[str, Any]:
        """Возвращает сводный отчет о проверках"""
        total_checks = len(self.check_results)
        consistent_checks = sum(1 for result in self.check_results if result.is_consistent)
        inconsistent_checks = total_checks - consistent_checks
        
        all_errors = []
        all_warnings = []
        
        for result in self.check_results:
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)
        
        return {
            'total_checks': total_checks,
            'consistent_checks': consistent_checks,
            'inconsistent_checks': inconsistent_checks,
            'consistency_rate': consistent_checks / total_checks if total_checks > 0 else 0,
            'total_errors': len(all_errors),
            'total_warnings': len(all_warnings),
            'errors': all_errors,
            'warnings': all_warnings
        }


def create_test_candle_data(price: float = 1000.0, time_offset: int = 0) -> Dict[str, Any]:
    """Создает тестовые данные свечи"""
    return {
        'time': datetime.now() - timedelta(minutes=time_offset),
        'open': price,
        'high': price + 5.0,
        'low': price - 5.0,
        'close': price + 2.0,
        'volume': 1000
    }


def create_test_signal_data(signal_type: str = 'buy', price: float = 1000.0, 
                          strength: float = 0.5) -> Dict[str, Any]:
    """Создает тестовые данные сигнала"""
    return {
        'time': datetime.now(),
        'type': signal_type,
        'strength': strength,
        'price': price,
        'macd': 0.3,
        'signal': 0.2,
        'histogram': 0.1
    }


def create_test_event(event_type: EventType, data: Dict[str, Any]) -> TradingEvent:
    """Создает тестовое событие"""
    return TradingEvent(event_type, data)


if __name__ == '__main__':
    # Пример использования
    event_bus = EventBus()
    checker = DataConsistencyChecker(event_bus)
    
    # Создаем тестовые данные
    candle_data = create_test_candle_data()
    signal_data = create_test_signal_data()
    event = create_test_event(EventType.CANDLE_RECEIVED, {'candle': Mock(), 'figi': 'TEST'})
    
    # Проверяем консистентность
    candle_result = checker.check_candle_data_consistency(candle_data, DataConsistencyLevel.COMPLETE)
    signal_result = checker.check_signal_data_consistency(signal_data, DataConsistencyLevel.COMPLETE)
    event_result = checker.check_event_data_consistency(event, DataConsistencyLevel.COMPLETE)
    
    print(f"Candle consistency: {candle_result.is_consistent}")
    print(f"Signal consistency: {signal_result.is_consistent}")
    print(f"Event consistency: {event_result.is_consistent}")

