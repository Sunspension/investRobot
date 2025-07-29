#!/usr/bin/env python3
"""
Использует модульную архитектуру для лучшей организации кода
"""

import asyncio
import sys
import threading
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import plotly.graph_objs as go
from dash import html, Input, Output, State, callback_context
from robotlib.utils.logger import get_logger

# Добавляем корневую папку проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config_data.config import load_config
from robotlib.trading.tinkoff_api_client import TinkoffAPIClient
from robotlib.signal_manager import SignalManager
from tinkoff.invest import CandleInterval
from robotlib.utils.tinkoff_market_hours import get_tinkoff_market_hours
from robotlib.utils.market_hours import MarketHours

# Импортируем наши модули
from visualization.data_manager import DataManager
from visualization.chart_builder import ChartBuilder
from visualization.ui_components import UIComponents
from visualization.trading_session_manager import TradingSessionManager

# Отключаем логи Tinkoff API
logging.getLogger('tinkoff.invest.logging').setLevel(logging.WARNING)

# Проверяем доступность реальных данных
try:
    config = load_config()
    REAL_DATA_AVAILABLE = bool(config.tcs_client.token)
except:
    REAL_DATA_AVAILABLE = False

class TradingSignalsVisualizer:
    """Визуализатор торговых сигналов"""
    
    def __init__(
        self, 
        data_manager: DataManager,
        chart_builder: ChartBuilder,
        ui_components: UIComponents,
        trading_session_manager: Optional[Any] = None,
        figi: str = "FUTIMOEXF000", 
        update_interval: int = 1
    ):
        """
        Инициализация визуализатора с инжектированными зависимостями
        
        Args:
            data_manager: Менеджер данных (обязательно)
            chart_builder: Строитель графиков (обязательно)
            ui_components: UI компоненты (обязательно)
            trading_session_manager: Менеджер торговой сессии (опционально)
            figi: FIGI инструмента для торговли
            update_interval: Интервал обновления в секундах
        """
        self.figi = figi
        self.update_interval = update_interval
        self.use_real_data = REAL_DATA_AVAILABLE
        
        if not self.use_real_data:
            raise RuntimeError("❌ Реальные данные недоступны! Проверьте настройки Tinkoff API в .env файле")
        self.logger = get_logger(__name__)
        
        # Состояние
        self.market_status: str = "🟡 Инициализация"
        self.is_running: bool = True
        
        # Лучшие параметры из оптимизации
        self.strategy_params = {
            'macd_fast': 6,
            'macd_slow': 16,
            'macd_signal': 7,
            'atr_period': 10,
            'lookback_min': 4,
            'lookback_max': 19,
            'peak_prominence': 0.15
        }
        
        # Инжектированные модули
        self.data_manager = data_manager
        self.chart_builder = chart_builder
        self.ui_components = ui_components
        self.trading_session_manager = trading_session_manager
        
        # API клиент
        self.config: Optional[Any] = None
        self.api_client: Optional[TinkoffAPIClient] = None
        
        # Фоновый поток
        self.data_thread: Optional[threading.Thread] = None
        self.stop_thread: bool = False
        
        # Инициализация компонентов
        self._initialize_components()
        
        # Создание Dash приложения
        self.app = self._create_dash_app()
        
        # Инициализация с историческими данными
        self._initialize_historical_data()
        
        # Запускаем фоновый поток для обновления данных
        if self.use_real_data:
            self.logger.info("🚀 Запускаем фоновый поток для реальных данных...")
            self._start_data_thread()
        else:
            self.logger.info("🎭 Используем симуляцию, запускаем фоновый поток...")
            self._start_data_thread()
    
    def _initialize_components(self):
        """Инициализирует компоненты для работы с данными"""
        try:
            if self.use_real_data:
                # Загружаем конфигурацию
                self.config = load_config()
                self.logger.info("Конфигурация загружена")
                
                
            else:
                raise RuntimeError("❌ Реальные данные недоступны! Проверьте настройки Tinkoff API в .env файле")
            
        except Exception as e:
            self.logger.error(f"Ошибка инициализации компонентов: {e}")
            raise RuntimeError(f"❌ Ошибка инициализации: {e}")
    
    def _initialize_historical_data(self):
        """Инициализирует исторические данные"""
        if not self.use_real_data:
            raise RuntimeError("❌ Реальные данные недоступны! Проверьте настройки Tinkoff API в .env файле")
        
        try:
            # Загружаем реальные исторические данные
            asyncio.run(self._load_real_historical_data())
        except Exception as e:
            self.logger.error(f"Ошибка инициализации исторических данных: {e}")
            raise RuntimeError(f"❌ Не удалось загрузить исторические данные: {e}")
    
    async def _load_real_historical_data(self):
        """Загружает реальные исторические данные"""
        try:
            if not self.config:
                self.logger.error("Конфигурация недоступна")
                return
            
            async with TinkoffAPIClient(
                token=self.config.tcs_client.token,
                account_id=self.config.tcs_client.id,
                sandbox_token=self.config.tcs_client.sandbox_token
            ) as api_client:
                # Получаем исторические данные
                to_date = datetime.now()
                from_date = to_date - timedelta(minutes=50)
                
                self.logger.info(f"🔄 Загружаем исторические данные с {from_date.strftime('%Y-%m-%d %H:%M')} по {to_date.strftime('%Y-%m-%d %H:%M')}")
                
                candles_response = await api_client.get_candles(
                    figi=self.figi,
                    from_date=from_date,
                    to_date=to_date,
                    interval=1
                )
                
                if candles_response and candles_response.candles:
                    self.logger.info(f"Загружено {len(candles_response.candles)} реальных свечей")
                    
                    for candle in candles_response.candles:
                        candle_data = {
                            'time': candle.time,
                            'open': candle.open.units + candle.open.nano / 1_000_000_000,
                            'high': candle.high.units + candle.high.nano / 1_000_000_000,
                            'low': candle.low.units + candle.low.nano / 1_000_000_000,
                            'close': candle.close.units + candle.close.nano / 1_000_000_000,
                            'volume': candle.volume
                        }
                        
                        self.data_manager.add_candle(candle_data)
                    
                    self.market_status = "📡 Реальные данные"
                    self.logger.info(f"✅ Загружено {len(self.data_manager.candles_data)} реальных свечей")
                    
                    # Предварительная подгрузка данных для стратегий
                    if self.trading_session_manager:
                        self.trading_session_manager.preload_strategy_data(self.data_manager.candles_data)
                else:
                    self.logger.error("❌ Не удалось получить реальные данные")
                    raise RuntimeError("❌ Не удалось получить реальные данные от Tinkoff API")
                    
        except Exception as e:
            self.logger.error(f"Ошибка загрузки реальных данных: {e}")
            raise RuntimeError(f"❌ Не удалось загрузить исторические данные: {e}")
    
    def _create_dash_app(self):
        """Создает Dash приложение"""
        app = self.ui_components.create_dash_app()
        
        # Callbacks
        @app.callback(
            [Output('trading-graph', 'figure'),
             Output('current-price', 'children'),
             Output('market-status', 'children'),
             Output('buy-count', 'children'),
             Output('sell-count', 'children'),
             Output('total-signals', 'children'),
             Output('orders-count', 'children'),
             Output('total-volume', 'children'),
             Output('strategy-status', 'children'),
             Output('trading-status', 'children'),
             Output('signals-list', 'children'),
             Output('recent-signals', 'children')],
            [Input('interval-component', 'n_intervals')],
            [State('simulation-state', 'data')],
            prevent_initial_call=True
        )
        def update_display(n, state):
            return self._update_display()
        
        @app.callback(
            Output('simulation-state', 'data'),
            [Input('start-btn', 'n_clicks'),
             Input('stop-btn', 'n_clicks'),
             Input('reset-btn', 'n_clicks'),
             Input('smart-data-btn', 'n_clicks'),
             Input('history-test-btn', 'n_clicks')],
            [State('simulation-state', 'data')]
        )
        def control_simulation(start_clicks, stop_clicks, reset_clicks, smart_data_clicks, history_test_clicks, state):
            ctx = callback_context
            if not ctx.triggered:
                return state
            
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            
            if button_id == 'start-btn':
                state['running'] = True
                self.is_running = True
                self.market_status = "🟢 Запущено"
                self._start_data_thread()
            elif button_id == 'stop-btn':
                state['running'] = False
                self.is_running = False
                self.market_status = "🔴 Остановлено"
            elif button_id == 'reset-btn':
                state['running'] = False
                self.is_running = False
                self.market_status = "🟡 Сброшено"
                self._reset_data()
            elif button_id == 'smart-data-btn':
                self._generate_smart_data()
            elif button_id == 'history-test-btn':
                self._run_history_test()
            
            return state
        
        return app
    
    def _update_display(self):
        """Обновляет отображение данных"""
        try:
            # Получаем снимок данных
            data_snapshot = self.data_manager.get_data_snapshot()
            
            # Обновляем ордера из TradingSession
            if self.trading_session_manager:
                orders_data = self.trading_session_manager.update_orders_from_trading_session()
                self.data_manager.update_orders(orders_data)
                data_snapshot = self.data_manager.get_data_snapshot()
            
            # Создаем график
            fig = self.chart_builder.create_trading_chart(
                candles_data=data_snapshot['candles_data'],
                signals_data=data_snapshot['signals_data'],
                orders_data=data_snapshot['orders_data'],
                current_price=data_snapshot['current_price']
            )
            
            # Создаем списки сигналов
            signals_list = self.ui_components.create_signals_list(data_snapshot['signals_data'])
            recent_signals = self.ui_components.create_recent_signals(data_snapshot['signals_data'])
            
            # Подсчитываем статистику
            total_signals = data_snapshot['buy_count'] + data_snapshot['sell_count']
            
            # Создаем статус стратегий
            strategy_status = self._get_strategy_status()
            
            # Создаем торговый статус
            trading_status = self._get_trading_status()
            
            # Получаем информацию о состоянии рынка
            market_info = self._get_market_status_info()
            enhanced_market_status = f"{market_info['status']} | {market_info['next_session']}"
            
            # Логируем цену для отладки
            self.logger.info(f"💰 Текущая цена: {data_snapshot['current_price']:.2f} ₽")
            
            return (
                fig,
                f"{float(data_snapshot['current_price']):.1f} ₽",
                enhanced_market_status,
                str(data_snapshot['buy_count']),
                str(data_snapshot['sell_count']),
                str(total_signals),
                str(data_snapshot['orders_count']),
                str(data_snapshot['total_volume']),
                strategy_status,
                trading_status,
                signals_list,
                recent_signals
            )
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления отображения: {e}")
            return (go.Figure(), "Ошибка", "❌ Ошибка", "0", "0", "0", "0", "0",
                   [html.P("Ошибка отображения")], [html.P("Ошибка отображения")], [html.P("Ошибка отображения")], [html.P("Ошибка отображения")])
    
    def _get_strategy_status(self):
        """Получает статус стратегий"""
        try:
            if not self.trading_session_manager:
                return [html.P("TradingSession недоступен", style={'color': '#666'})]
            
            strategy_status = []
            strategies = self.trading_session_manager.get_strategy_status()
            
            for strategy in strategies:
                status_color = '#00ff88' if strategy['income'] >= 0 else '#ff4444'
                position_color = '#2E86AB' if strategy['position'] == 0 else ('#28a745' if strategy['position'] > 0 else '#dc3545')
                
                strategy_status.append(
                    html.Div([
                        html.Div([
                            html.Span(f"📊 {strategy['name']}", 
                                     style={'fontWeight': 'bold', 'color': '#2E86AB', 'fontSize': '0.9em'}),
                            html.Br(),
                            html.Span(f"Доход: {strategy['income']:.2f} ₽", 
                                     style={'color': status_color, 'fontSize': '0.8em'}),
                            html.Br(),
                            html.Span(f"Позиция: {strategy['position']}", 
                                     style={'color': position_color, 'fontSize': '0.8em'})
                        ])
                    ], style={
                        'padding': '8px', 
                        'marginBottom': '8px', 
                        'border': '1px solid #eee',
                        'borderRadius': '5px',
                        'backgroundColor': '#f8f9fa'
                    })
                )
            
            if not strategy_status:
                strategy_status = [html.P("Стратегии не инициализированы", style={'color': '#666'})]
            
            return strategy_status
            
        except Exception as e:
            self.logger.error(f"Ошибка получения статуса стратегий: {e}")
            return [html.P("Ошибка загрузки статуса", style={'color': '#dc3545'})]
    
    def _get_trading_status(self):
        """Получает торговый статус"""
        try:
            # Используем статическое расписание как fallback
            status = MarketHours.get_trading_status()
            current_time = status['current_time']
            is_trading = status['is_trading']
            next_session = status['next_session']
            
            # Определяем цвет статуса
            status_color = '#28a745' if is_trading else '#dc3545'
            status_text = "🟢 Торговля идет" if is_trading else "🔴 Торговля закрыта"
            
            status_elements = [
                html.P(status_text, style={'margin': '5px 0', 'fontWeight': 'bold', 'color': status_color}),
                html.P(f"Время: {current_time.strftime('%H:%M:%S')}", style={'margin': '2px 0', 'color': '#6c757d'})
            ]
            
            if next_session:
                next_start = next_session['start']
                time_until = next_start - current_time
                hours = int(time_until.total_seconds() // 3600)
                minutes = int((time_until.total_seconds() % 3600) // 60)
                
                status_elements.append(
                    html.P(f"Следующая сессия: {next_start.strftime('%H:%M')}", style={'margin': '2px 0', 'color': '#6c757d'})
                )
                status_elements.append(
                    html.P(f"До начала: {hours}ч {minutes}м", style={'margin': '2px 0', 'color': '#6c757d'})
                )
            
            return status_elements
            
        except Exception as e:
            self.logger.error(f"Ошибка получения торгового статуса: {e}")
            return [html.P("Ошибка загрузки статуса", style={'color': '#dc3545'})]
    
    def _get_market_status_info(self):
        """Получает информацию о состоянии рынка"""
        try:
            now = datetime.now()
            current_time = now.time()
            
            # Определяем состояние рынка для фьючерса на MOEX
            morning_start = datetime.strptime("10:00", "%H:%M").time()
            morning_end = datetime.strptime("18:45", "%H:%M").time()
            evening_start = datetime.strptime("19:05", "%H:%M").time()
            evening_end = datetime.strptime("23:50", "%H:%M").time()
            
            is_morning_session = morning_start <= current_time <= morning_end
            is_evening_session = evening_start <= current_time <= evening_end
            is_weekend = now.weekday() >= 5
            
            if is_weekend:
                status = "🔴 Выходной"
                next_session = "Понедельник 10:00"
            elif is_morning_session:
                status = "🟢 Утренняя сессия"
                next_session = "19:05 (вечерняя)"
            elif is_evening_session:
                status = "🟡 Вечерняя сессия"
                next_session = "Завтра 10:00"
            elif current_time < morning_start:
                status = "⏰ До открытия"
                next_session = "10:00 (утренняя)"
            elif morning_end < current_time < evening_start:
                status = "⏸️ Перерыв"
                next_session = "19:05 (вечерняя)"
            else:
                status = "🔴 Закрыто"
                next_session = "Завтра 10:00"
            
            return {
                'status': status,
                'next_session': next_session,
                'current_time': current_time.strftime("%H:%M:%S"),
                'is_trading': is_morning_session or is_evening_session
            }
        except Exception as e:
            self.logger.error(f"Ошибка определения состояния рынка: {e}")
            return {
                'status': "❓ Неизвестно",
                'next_session': "Неизвестно",
                'current_time': datetime.now().strftime("%H:%M:%S"),
                'is_trading': False
            }
    
    def _start_data_thread(self):
        """Запускает фоновый поток для обновления данных"""
        if self.data_thread is None or not self.data_thread.is_alive():
            self.stop_thread = False
            self.data_thread = threading.Thread(target=self._data_update_loop, daemon=True)
            self.data_thread.start()
            self.logger.info("Фоновый поток для обновления данных запущен")
    
    def _stop_data_thread(self):
        """Останавливает фоновый поток"""
        self.stop_thread = True
        if self.data_thread and self.data_thread.is_alive():
            self.data_thread.join(timeout=2)
            self.logger.info("Фоновый поток остановлен")
    
    def _data_update_loop(self):
        """Основной цикл обновления данных в фоновом потоке"""
        self.logger.info("🔄 Фоновый поток обновления данных запущен")
        while not self.stop_thread:
            try:
                # Создаем новый event loop для этого потока
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._fetch_real_data())
                finally:
                    loop.close()
                
            except Exception as e:
                self.logger.error(f"❌ Ошибка в фоновом потоке: {e}")
            
            # Ждем до следующего обновления
            time.sleep(self.update_interval)
    
    async def _fetch_real_data(self):
        """Получает новые реальные данные"""
        try:
            if not self.config:
                return
            
            async with TinkoffAPIClient(
                token=self.config.tcs_client.token,
                account_id=self.config.tcs_client.id,
                sandbox_token=self.config.tcs_client.sandbox_token
            ) as api_client:
                # Получаем последние свечи
                to_date = datetime.now()
                from_date = to_date - timedelta(minutes=1)
                
                candles_response = await api_client.get_candles(
                    figi=self.figi,
                    from_date=from_date,
                    to_date=to_date,
                    interval=1
                )
                
                if candles_response and candles_response.candles:
                    for candle in candles_response.candles:
                        candle_data = {
                            'time': candle.time,
                            'open': candle.open.units + candle.open.nano / 1_000_000_000,
                            'high': candle.high.units + candle.high.nano / 1_000_000_000,
                            'low': candle.low.units + candle.low.nano / 1_000_000_000,
                            'close': candle.close.units + candle.close.nano / 1_000_000_000,
                            'volume': candle.volume
                        }
                        
                        # Проверяем, есть ли уже такая свеча
                        existing_times = {candle['time'] for candle in self.data_manager.candles_data}
                        if candle_data['time'] not in existing_times:
                            self.data_manager.add_candle(candle_data)
                            
                            # Проверяем сигналы через TradingSession
                            if self.trading_session_manager:
                                signals = await self.trading_session_manager.get_trading_session_signals(candle)
                                for signal in signals:
                                    self.data_manager.add_signal(signal)
                            
        except Exception as e:
            self.logger.error(f"Ошибка получения реальных данных: {e}")
    
    def _reset_data(self):
        """Сбрасывает данные"""
        self.data_manager.reset_data()
        if self.trading_session_manager:
            self.trading_session_manager.reset_strategies()
        self._initialize_historical_data()
    
    def _generate_smart_data(self):
        """Генерирует умные данные, которые должны вызвать срабатывание стратегий"""
        self.logger.info("🧠 Генерируем умные данные для стратегий...")
        # Реализация генерации умных данных
        pass
    
    def _run_history_test(self):
        """Запускает тест стратегий на исторических данных"""
        self.logger.info("🧪 Запускаем тест стратегий на исторических данных...")
        # Реализация тестирования на истории
        pass
    
    def run(self, host: str = "127.0.0.1", port: int = 8050, debug: bool = False):
        """Запускает визуализацию"""
        self.logger.info(f"Запуск визуализации с {'реальными' if self.use_real_data else 'симулированными'} данными на http://{host}:{port}")
        try:
            # Пытаемся запустить на указанном порту, если занят - пробуем другие
            for attempt_port in range(port, port + 10):
                try:
                    self.logger.info(f"Попытка запуска на порту {attempt_port}")
                    self.app.run(host=host, port=attempt_port, debug=debug)
                    break
                except OSError as e:
                    if "Address already in use" in str(e):
                        self.logger.warning(f"Порт {attempt_port} занят, пробуем {attempt_port + 1}")
                        continue
                    else:
                        raise
        finally:
            self._stop_data_thread()


def main():
    """Главная функция"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Отключаем избыточные логи
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('dash').setLevel(logging.WARNING)
    logging.getLogger('tinkoff.invest.logging').setLevel(logging.WARNING)
    
    try:
        visualizer = TradingSignalsVisualizer(
            figi="FUTIMOEXF000",
            update_interval=1,
            use_real_data=True
        )
        visualizer.run()
    except KeyboardInterrupt:
        print("\n👋 Визуализация остановлена пользователем")
    except Exception as e:
        print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    main()
