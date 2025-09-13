"""
Адаптер для интеграции TradingSignalsVisualizer с торговой системой
"""
import asyncio
import threading
import time
import concurrent.futures
from typing import Dict, Any, Optional, List
from datetime import datetime
from robotlib.utils.logger import get_logger
from robotlib.trading.visualizer_interface import TradingVisualizerable
from robotlib.utils.market_hours import get_market_status_with_api
from robotlib.utils.market_hours_enhanced import get_market_status_enhanced

# Импортируем компоненты визуализатора
from visualization.data_manager import DataManager
from visualization.chart_builder import ChartBuilder
from visualization.ui_components import UIComponents
from visualization.interfaces import (
    StrategyDataProvider, 
    TradingSessionDataProvider, 
    MockStrategyDataProvider,
    DataManagerable,
    ChartBuilderable,
    UIComponentsable
)
from visualization.logging_config import disable_verbose_logging, QuietFlaskServer

# Dash импорты
from dash import Dash, dcc, html, Input, Output, State, callback_context
from plotly.graph_objects import Figure


class TradingVisualizerAdapter(TradingVisualizerable):
    """Адаптер для интеграции TradingSignalsVisualizer с торговой системой"""
    
    def __init__(
        self, 
        data_manager: DataManagerable,
        chart_builder: ChartBuilderable,
        ui_components: UIComponentsable,
        strategy_data_provider: StrategyDataProvider,
        figi: str = "FUTIMOEXF000",
        update_interval: int = 1,
        host: str = "127.0.0.1",
        port: int = 8050
    ):
        """
        Инициализация адаптера визуализатора
        
        Args:
            data_manager: Менеджер данных
            chart_builder: Построитель графиков
            ui_components: UI компоненты
            strategy_data_provider: Провайдер данных о стратегиях
            figi: FIGI инструмента
            update_interval: Интервал обновления в секундах
            host: Хост для веб-интерфейса
            port: Порт для веб-интерфейса
        """
        self._figi = figi
        self._update_interval = update_interval
        self._host = host
        self._port = port
        self._logger = get_logger(__name__)
        
        # Состояние
        self._running = False
        self._app = None
        self._server_thread = None
        
        # Кэш для API данных
        self._market_status_cache = None
        self._last_cache_update = None
        self._cache_ttl = 30  # Кэш на 30 секунд
        
        # Зависимости (инжектируются)
        self._data_manager = data_manager
        self._chart_builder = chart_builder
        self._ui_components = ui_components
        self._strategy_data_provider = strategy_data_provider
        
        # Отключаем избыточные логи
        self._disable_verbose_logging()
    
    def update_strategy_data_provider(self, session_controller) -> None:
        """
        Обновляет провайдер данных стратегий на реальный
        
        Args:
            session_controller: Контроллер торговой сессии
        """
        try:
            from visualization.interfaces import TradingSessionDataProvider
            
            # Создаем реальный провайдер данных
            real_provider = TradingSessionDataProvider(session_controller)
            self._strategy_data_provider = real_provider
            
            self._logger.info("✅ Провайдер данных стратегий обновлен на реальный")
            
        except Exception as e:
            self._logger.error(f"❌ Ошибка обновления провайдера данных: {e}")
        
        # Инициализация
        self._initialize_components()
    
    def is_running(self) -> bool:
        """Проверяет, запущен ли визуализатор"""
        return self._running
    
    def _disable_verbose_logging(self):
        """Отключает избыточные логи Flask/Dash"""
        disable_verbose_logging()
    
    def _initialize_components(self):
        """Инициализирует компоненты визуализатора"""
        try:
            # Создаем Dash приложение
            self._app = self._create_dash_app()
            self._logger.info("Компоненты визуализатора инициализированы")
        except Exception as e:
            self._logger.error(f"Ошибка инициализации компонентов: {e}")
            raise
    
    def _create_dash_app(self):
        """Создает Dash приложение"""
        app = Dash(__name__)
        
        # Стили
        app.index_string = self._ui_components._get_custom_html_template()
        
        # Layout
        app.layout = self._ui_components._create_layout()
        
        # Callbacks
        @app.callback(
            [Output('trading-graph', 'figure'),
             Output('current-price', 'children'),
             Output('market-status', 'children'),
             Output('buy-count', 'children'),
             Output('sell-count', 'children'),
             Output('orders-count', 'children'),
             Output('total-volume', 'children'),
             Output('strategy-status', 'children'),
             Output('trading-status', 'children'),
             Output('signals-list', 'children'),
             Output('recent-signals', 'children'),
            Output('portfolio-balance', 'children'),
            Output('portfolio-pnl', 'children'),
            Output('portfolio-variation-margin', 'children'),
            Output('portfolio-guarantee-deposit', 'children')],
            [Input('interval-component', 'n_intervals'),
             Input('start-btn', 'n_clicks'),
             Input('stop-btn', 'n_clicks')],
            [State('simulation-state', 'data')],
            prevent_initial_call=False  # Включаем начальное обновление
        )
        def update_display(n, start_clicks, stop_clicks, state):
            self._logger.info("🔄 Callback update_display вызван")
            
            # Обновляем при нажатии кнопок или каждые 60 секунд
            ctx = callback_context
            if not ctx.triggered:
                self._logger.info("🔄 Нет триггеров, вызываем _update_display")
                result = self._update_display()
                return result
            
            # Проверяем, что это обновление по интервалу или кнопкам
            trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
            self._logger.info(f"🔄 Триггер: {trigger_id}")
            
            if trigger_id == 'interval-component':
                # Редкие обновления каждые 60 секунд - проверяем изменения
                self._logger.info("🔄 Обновление по интервалу")
                result = self._update_display_if_changed()
                return result
            else:
                # При нажатии кнопок обновляем сразу
                self._logger.info("🔄 Обновление по кнопке")
                result = self._update_display()
                return result
        
        @app.callback(
            Output('simulation-state', 'data'),
            [Input('start-btn', 'n_clicks'),
             Input('stop-btn', 'n_clicks')],
            [State('simulation-state', 'data')]
        )
        def control_simulation(start_clicks, stop_clicks, state):
            ctx = callback_context
            if not ctx.triggered:
                return state
            
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            
            if button_id == 'start-btn':
                state['running'] = True
            elif button_id == 'stop-btn':
                state['running'] = False
            
            return state
        
        # Дополнительный callback для принудительного обновления при загрузке страницы
        @app.callback(
            Output('trading-graph', 'figure', allow_duplicate=True),
            [Input('interval-component', 'n_intervals')],
            prevent_initial_call='initial_duplicate'
        )
        def force_initial_update(n):
            """Принудительно обновляет график при загрузке страницы"""
            self._logger.info("🔄 Принудительное обновление графика при загрузке...")
            try:
                data_snapshot = self._data_manager.get_data_snapshot()
                fig = self._chart_builder.create_trading_chart(
                    candles_data=data_snapshot['candles_data'],
                    signals_data=data_snapshot['signals_data'],
                    orders_data=data_snapshot['orders_data'],
                    current_price=data_snapshot['current_price']
                )
                return fig
            except Exception as e:
                self._logger.error(f"Ошибка принудительного обновления графика: {e}")
                return Figure()
        
        # Callback для динамического цвета P&L
        @app.callback(
            Output('portfolio-pnl', 'style'),
            [Input('interval-component', 'n_intervals')],
            prevent_initial_call=False
        )
        def update_pnl_color(n):
            """Обновляет цвет P&L в зависимости от значения"""
            try:
                data_snapshot = self._data_manager.get_data_snapshot()
                portfolio_data = data_snapshot.get('portfolio_data', {})
                pnl_value = portfolio_data.get('pnl', 0)
                
                # Определяем цвет на основе значения P&L
                if pnl_value > 0:
                    color = '#28a745'  # Зеленый для прибыли
                elif pnl_value < 0:
                    color = '#dc3545'  # Красный для убытка
                else:
                    color = '#6c757d'  # Серый для нуля
                
                return {'color': color}
            except Exception as e:
                self._logger.error(f"Ошибка обновления цвета P&L: {e}")
                return {'color': '#6c757d'}  # Серый по умолчанию
        
        # Callback для динамического цвета вариационной маржи
        @app.callback(
            Output('portfolio-variation-margin', 'style'),
            [Input('interval-component', 'n_intervals')],
            prevent_initial_call=False
        )
        def update_variation_margin_color(n):
            """Обновляет цвет вариационной маржи в зависимости от значения"""
            try:
                data_snapshot = self._data_manager.get_data_snapshot()
                portfolio_data = data_snapshot.get('portfolio_data', {})
                variation_margin_value = portfolio_data.get('variation_margin', 0)
                
                # Определяем цвет на основе значения вариационной маржи
                if variation_margin_value > 0:
                    color = '#28a745'  # Зеленый для положительной вариационной маржи
                elif variation_margin_value < 0:
                    color = '#dc3545'  # Красный для отрицательной вариационной маржи
                else:
                    color = '#6c757d'  # Серый для нуля
                
                return {'color': color}
            except Exception as e:
                self._logger.error(f"Ошибка обновления цвета вариационной маржи: {e}")
                return {'color': '#6c757d'}  # Серый по умолчанию
        
        return app
    
    def _update_display(self):
        """Обновляет отображение данных"""
        try:
            # Получаем снимок данных
            data_snapshot = self._data_manager.get_data_snapshot()
            
            # Создаем график
            fig = self._chart_builder.create_trading_chart(
                candles_data=data_snapshot['candles_data'],
                signals_data=data_snapshot['signals_data'],
                orders_data=data_snapshot['orders_data'],
                current_price=data_snapshot['current_price']
            )
            
            # Создаем списки сигналов
            signals_list = self._ui_components.create_signals_list(data_snapshot['signals_data'])
            recent_signals = self._ui_components.create_recent_signals(data_snapshot['signals_data'])
            
            # Подсчитываем статистику (убрали total_signals)
            
            # Получаем данные о стратегиях
            strategies_data = self._get_strategies_data()
            self._data_manager.update_strategies_data(strategies_data)
            
            # Создаем статус стратегий
            strategy_status = self._get_strategy_status()
            
            # Создаем торговый статус
            trading_status = self._get_trading_status()
            
            # Получаем информацию о состоянии рынка
            market_info = self._get_market_status_info()
            
            if isinstance(market_info, dict):
                # Форматируем информацию о рынке более читаемо
                status = market_info['status']
                session_info = market_info['session_info']
                next_session = market_info['next_session']
                
                # Создаем красивое отображение
                if session_info and session_info != "Торговая сессия активна":
                    enhanced_market_status = f"{status} {session_info}"
                    if next_session:
                        enhanced_market_status += f" • {next_session}"
                else:
                    enhanced_market_status = f"{status} {next_session}"
            else:
                # Если это HTML элементы, используем их напрямую
                enhanced_market_status = market_info
            
            
            # Получаем данные портфеля
            portfolio_data = data_snapshot.get('portfolio_data', {})
            portfolio_balance = f"{portfolio_data.get('total_amount', 0):.2f} ₽"
            
            # P&L с динамическим цветом
            pnl_value = portfolio_data.get('pnl', 0)
            portfolio_pnl = f"{pnl_value:.2f} ₽"
            
            portfolio_variation_margin = f"{portfolio_data.get('variation_margin', 0):.2f} ₽"
            portfolio_guarantee_deposit = f"{portfolio_data.get('guarantee_deposit', 0):.2f} ₽"
            
            result = (
                fig,
                f"{float(data_snapshot['current_price']):.1f} ₽",
                enhanced_market_status,
                str(data_snapshot['buy_count']),
                str(data_snapshot['sell_count']),
                str(data_snapshot['orders_count']),
                str(data_snapshot['total_volume']),
                strategy_status,
                trading_status,
                signals_list,
                recent_signals,
                portfolio_balance,
                portfolio_pnl,
                portfolio_variation_margin,
                portfolio_guarantee_deposit
            )
            
            return result
            
        except Exception as e:
            self._logger.error(f"Ошибка обновления отображения: {e}")
            return (Figure(), "Ошибка", "❌ Ошибка", "0", "0", "0", "0",
                   [html.P("Ошибка отображения")], [html.P("Ошибка отображения")], [html.P("Ошибка отображения")], [html.P("Ошибка отображения")],
                   "0.00 ₽", "0.00 ₽", "0.00 ₽", "0.00 ₽")
    
    def _update_display_if_changed(self):
        """Обновляет отображение"""
        try:
            # Всегда обновляем отображение без кэширования
            self._logger.info("🔄 Обновляем отображение")
            result = self._update_display()
            return result
            
        except Exception as e:
            self._logger.error(f"Ошибка обновления отображения: {e}")
            return self._update_display()
    
    def _get_strategy_status(self):
        """Получает статус стратегий"""
        try:
            # Получаем данные из DataManager
            data_snapshot = self._data_manager.get_data_snapshot()
            
            # Получаем данные о стратегиях
            strategies_data = data_snapshot.get('strategies_data', [])
            
            if not strategies_data:
                # Если нет данных о стратегиях, показываем общий статус
                strategy_status = data_snapshot.get('strategy_status', 'Инициализация...')
                
                if 'Инициализация' in strategy_status:
                    return [html.P(f"🔄 {strategy_status}", style={'color': '#ffc107'})]
                elif 'Активна' in strategy_status or 'Active' in strategy_status:
                    return [html.P(f"✅ {strategy_status}", style={'color': '#28a745'})]
                else:
                    return [html.P(f"ℹ️ {strategy_status}", style={'color': '#17a2b8'})]
            
            # Создаем детальный статус для каждой стратегии
            strategy_elements = []
            
            for strategy in strategies_data:
                strategy_name = strategy.get('name', 'Unknown')
                position = strategy.get('position', 0)
                income = strategy.get('income', 0.0)
                
                # Определяем тип стратегии и статус
                if 'Long' in strategy_name:
                    strategy_type = "Лонг"
                    if position > 0:
                        status_text = "Ожидание сигнала на закрытие лонга"
                        color = '#28a745'  # Зеленый для открытой позиции
                    else:
                        status_text = "Ожидание сигнала на открытие лонга"
                        color = '#ffc107'  # Желтый для ожидания
                elif 'Short' in strategy_name:
                    strategy_type = "Шорт"
                    if position > 0:
                        status_text = "Ожидание сигнала на закрытие шорта"
                        color = '#dc3545'  # Красный для открытой позиции
                    else:
                        status_text = "Ожидание сигнала на открытие шорта"
                        color = '#ffc107'  # Желтый для ожидания
                else:
                    strategy_type = "Неизвестно"
                    status_text = "Неизвестный статус"
                    color = '#6c757d'  # Серый
                
                # Создаем элемент для стратегии
                strategy_element = html.Div([
                    html.P(f"📊 {strategy_type} стратегия", style={'fontWeight': 'bold', 'marginBottom': '5px', 'textAlign': 'left'}),
                    html.P(f"Позиция: {position}", style={'marginBottom': '2px', 'fontSize': '14px', 'textAlign': 'left'}),
                    html.P(f"Статус: {status_text}", style={'color': color, 'fontSize': '12px', 'textAlign': 'left'})
                ], style={'marginBottom': '10px', 'padding': '8px', 'border': '1px solid #dee2e6', 'borderRadius': '4px', 'textAlign': 'left'})
                
                strategy_elements.append(strategy_element)
            
            return strategy_elements
            
        except Exception as e:
            self._logger.error(f"Ошибка получения статуса стратегий: {e}")
            return [html.P("❌ Ошибка загрузки стратегий", style={'color': '#dc3545'})]
    
    def _get_trading_status(self):
        """Получает торговый статус"""
        try:
            # Получаем данные из DataManager
            data_snapshot = self._data_manager.get_data_snapshot()
            
            # Создаем более информативный статус
            candle_count = len(data_snapshot.get('candles_data', []))
            signal_count = data_snapshot.get('buy_count', 0) + data_snapshot.get('sell_count', 0)
            current_price = data_snapshot.get('current_price', 0.0)
            last_update = data_snapshot.get('last_update')
            
            # Форматируем время последнего обновления
            if last_update:
                time_str = last_update.strftime("%H:%M:%S")
            else:
                time_str = "неизвестно"
            
            # Создаем статус на основе данных
            if candle_count > 0:
                if signal_count > 0:
                    status = f"🟢 Торговля активна • {signal_count} сигналов • {candle_count} свечей • {current_price:.2f}₽ • {time_str}"
                    color = '#28a745'
                else:
                    # Показываем более полезную информацию вместо "Мониторинг"
                    orders_count = data_snapshot.get('orders_count', 0)
                    total_volume = data_snapshot.get('total_volume', 0)
                    
                    # Получаем информацию о портфеле
                    portfolio_data = data_snapshot.get('portfolio_data', {})
                    positions_count = len(portfolio_data.get('positions', []))
                    pnl_value = portfolio_data.get('pnl', 0)
                    
                    # Формируем статус с информацией о портфеле
                    if positions_count > 0:
                        pnl_sign = "+" if pnl_value >= 0 else ""
                        status = f"🟡 Ожидание сигналов • {candle_count} свечей • {positions_count} позиций • P&L: {pnl_sign}{pnl_value:.2f}₽ • {time_str}"
                    else:
                        status = f"🟡 Ожидание сигналов • {candle_count} свечей • {orders_count} ордеров • {current_price:.2f}₽ • {time_str}"
                    
                    color = '#ffc107'
            else:
                # Получаем информацию о рынке
                market_info = self._get_market_status_info()
                if isinstance(market_info, dict) and 'status' in market_info:
                    # Используем информацию о рынке
                    status = market_info['status']
                    if 'session_info' in market_info and market_info['session_info']:
                        status += f" {market_info['session_info']}"
                    if 'next_session' in market_info and market_info['next_session']:
                        status += f" • {market_info['next_session']}"
                    
                    # Добавляем индикатор типа данных
                    if not market_info.get('is_trading', False):
                        # Проверяем, есть ли свечи в кэше
                        data_snapshot = self._data_manager.get_data_snapshot()
                        historical_candles = len(data_snapshot.get('candles_data', []))
                        if historical_candles > 0:
                            status += f" • 📊 Исторические данные ({historical_candles} свечей)"
                        else:
                            # Если данных еще нет, но рынок закрыт, показываем что загружаем
                            status += " • 📊 Загрузка исторических данных..."
                            self._logger.info("⏳ Показываем индикатор загрузки исторических данных")
                    else:
                        # Рынок открыт - показываем тип активной сессии
                        session_type = market_info.get('session_type', 'unknown')
                        if session_type == 'weekend':
                            status += " • 🏖️ Выходные торги"
                        elif session_type == 'evening':
                            status += " • 🌙 Вечерние торги"
                        elif session_type == 'main':
                            status += " • 📈 Основные торги"
                    
                    color = '#17a2b8'
                else:
                    status = "🔄 Подключение к рынку..."
                    color = '#17a2b8'
            
            # Добавляем индикатор типа данных (независимо от candle_count)
            if candle_count > 0:
                market_info = self._get_market_status_info()
                if isinstance(market_info, dict):
                    if not market_info.get('is_trading', False):
                        # Рынок закрыт - показываем исторические данные
                        data_snapshot = self._data_manager.get_data_snapshot()
                        historical_candles = len(data_snapshot.get('candles_data', []))
                        if historical_candles > 0:
                            status += f" • 📊 Исторические данные ({historical_candles} свечей)"
                        else:
                            status += " • 📊 Загрузка исторических данных..."
                            self._logger.info("⏳ Показываем индикатор загрузки исторических данных (candle_count>0)")
                    else:
                        # Рынок открыт - показываем тип активной сессии
                        session_type = market_info.get('session_type', 'unknown')
                        if session_type == 'weekend':
                            status += " • 🏖️ Выходные торги"
                        elif session_type == 'evening':
                            status += " • 🌙 Вечерние торги"
                        elif session_type == 'main':
                            status += " • 📈 Основные торги"
            
            return [html.P(status, style={'color': color, 'fontWeight': 'bold', 'fontSize': '14px'})]
            
        except Exception as e:
            self._logger.error(f"Ошибка получения торгового статуса: {e}")
            return [html.P("❌ Ошибка загрузки статуса", style={'color': '#dc3545'})]
    
    def _get_market_status_info(self):
        """Получает информацию о состоянии рынка"""
        # Проверяем кэш
        if (self._market_status_cache and 
            self._last_cache_update and 
            (datetime.now() - self._last_cache_update).seconds < self._cache_ttl):
            return self._market_status_cache
        
        try:
            # Получаем данные из расширенного API с поддержкой выходных торгов
            
            # Проверяем, есть ли уже запущенный event loop
            try:
                loop = asyncio.get_running_loop()
                # Если есть, используем его
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, get_market_status_enhanced())
                    market_data = future.result()
            except RuntimeError:
                # Нет запущенного loop, создаем новый
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    market_data = loop.run_until_complete(get_market_status_enhanced())
                finally:
                    loop.close()
            
            # Обрабатываем данные из расширенного API
            is_trading = market_data.get('is_trading', False)
            current_time = market_data.get('current_time', datetime.now())
            next_session = market_data.get('next_session')
            session_type = market_data.get('session_type', 'unknown')
            is_weekend_trading = market_data.get('is_weekend_trading', False)
            is_evening_trading = market_data.get('is_evening_trading', False)
            
            # Форматируем статус на основе расширенных данных API
            if is_trading:
                status = "🟢"
                
                # Определяем тип активной сессии
                if is_weekend_trading:
                    session_info = "🏖️ Выходные торги"
                elif is_evening_trading:
                    session_info = "🌙 Вечерние торги"
                else:
                    session_info = "📈 Основные торги"
            else:
                status = "🔴"
                session_info = "Торговая сессия закрыта"
            
            # Форматируем информацию о следующей сессии
            if next_session and 'session' in next_session:
                session_name = next_session['session'].get('name', 'Торговая сессия')
                session_start = next_session.get('start')
                session_end = next_session.get('end')
                
                if session_start and session_end:
                    if hasattr(session_start, 'strftime') and hasattr(session_end, 'strftime'):
                        next_session_str = f"{session_name}: {session_start.strftime('%H:%M')} - {session_end.strftime('%H:%M')}"
                    else:
                        next_session_str = f"{session_name}: {session_start} - {session_end}"
                elif session_start:
                    if hasattr(session_start, 'strftime'):
                        next_session_str = f"{session_name}: {session_start.strftime('%H:%M')}"
                    else:
                        next_session_str = f"{session_name}: {session_start}"
                else:
                    next_session_str = f"Следующая сессия: {session_name}"
            else:
                # Если нет информации о следующей сессии, показываем текущее время
                next_session_str = f"Текущее время: {current_time.strftime('%H:%M:%S') if hasattr(current_time, 'strftime') else str(current_time)}"
            
            result = {
                'status': status,
                'next_session': next_session_str,
                'session_info': session_info,
                'current_time': current_time.strftime("%H:%M:%S") if hasattr(current_time, 'strftime') else str(current_time),
                'is_trading': is_trading
            }
            
            # Сохраняем в кэш
            self._market_status_cache = result
            self._last_cache_update = datetime.now()
            
            return result
                
        except Exception as e:
            self._logger.error(f"Ошибка получения данных из API: {e}")
            
            # При ошибке API показываем явную ошибку
            current_time = datetime.now()
            
            result = {
                'status': "❌ Ошибка API",
                'next_session': f"Текущее время: {current_time.strftime('%H:%M:%S')}",
                'session_info': f"Ошибка подключения к Tinkoff API: {str(e)[:50]}...",
                'current_time': current_time.strftime("%H:%M:%S"),
                'is_trading': False
            }
            
            # Сохраняем в кэш даже при ошибке (временно отключаем для отладки)
            # self._market_status_cache = result
            # self._last_cache_update = datetime.now()
            
            return result
    
    async def add_candle(self, candle_data: Dict[str, Any]) -> None:
        """Добавляет свечу в визуализатор"""
        try:
            self._data_manager.add_candle(candle_data)
            self._logger.debug(f"Добавлена свеча: {candle_data.get('time', 'N/A')}")
            
            # Принудительно обновляем интерфейс при добавлении свечи
            await self.force_update()
        except Exception as e:
            self._logger.error(f"Ошибка добавления свечи: {e}")
    
    async def force_update(self) -> None:
        """Принудительно обновляет интерфейс"""
        try:
            # Принудительное обновление интерфейса (кэширование убрано)
            self._logger.debug("Принудительное обновление интерфейса")
        except Exception as e:
            self._logger.error(f"Ошибка принудительного обновления: {e}")
    
    async def add_signal(self, signal_data: Dict[str, Any]) -> None:
        """Добавляет торговый сигнал в визуализатор"""
        try:
            self._data_manager.add_signal(signal_data)
            self._logger.debug(f"Добавлен сигнал: {signal_data.get('type', 'N/A')} по цене {signal_data.get('price', 'N/A')}")
        except Exception as e:
            self._logger.error(f"Ошибка добавления сигнала: {e}")
    
    async def add_order(self, order_data: Dict[str, Any]) -> None:
        """Добавляет ордер в визуализатор"""
        try:
            self._data_manager.add_order(order_data)
            self._logger.debug(f"Добавлен ордер: {order_data.get('type', 'N/A')} по цене {order_data.get('price', 'N/A')}")
        except Exception as e:
            self._logger.error(f"Ошибка добавления ордера: {e}")
    
    async def update_portfolio(self, portfolio_data: Dict[str, Any]) -> None:
        """Обновляет информацию о портфеле в визуализаторе"""
        try:
            self._data_manager.update_portfolio(portfolio_data)
            self._logger.debug(f"Обновлен портфель: баланс={portfolio_data.get('total_amount', 0):.2f}, PnL={portfolio_data.get('pnl', 0):.2f}")
        except Exception as e:
            self._logger.error(f"Ошибка обновления портфеля: {e}")
    
    async def update_market_status(self, status_data: Dict[str, Any]) -> None:
        """Обновляет статус рынка в визуализаторе"""
        try:
            # Здесь можно добавить логику обновления статуса рынка
            self._logger.debug(f"Обновлен статус рынка: {status_data}")
        except Exception as e:
            self._logger.error(f"Ошибка обновления статуса рынка: {e}")
    
    async def update_strategies_data(self, strategies_data: List[Dict[str, Any]]) -> None:
        """Обновляет данные о стратегиях в визуализаторе"""
        try:
            self._data_manager.update_strategies_data(strategies_data)
            self._logger.debug(f"Обновлены данные стратегий: {len(strategies_data)} стратегий")
        except Exception as e:
            self._logger.error(f"Ошибка обновления данных стратегий: {e}")
    
    async def start(self) -> None:
        """Запускает визуализатор"""
        if self._running:
            self._logger.warning("Визуализатор уже запущен")
            return
        
        try:
            self._running = True
            
            # Запускаем сервер в отдельном потоке
            self._server_thread = threading.Thread(
                target=self._run_server, 
                daemon=True
            )
            self._server_thread.start()
            
            # Ждем запуска сервера
            time.sleep(2)
            
            # Принудительно обновляем данные при запуске
            try:
                self._logger.info("🔄 Принудительное обновление данных при запуске...")
                self._update_display()
            except Exception as e:
                self._logger.error(f"Ошибка принудительного обновления: {e}")
            
            self._logger.info(f"Визуализатор запущен на http://{self._host}:{self._port}")
            
        except Exception as e:
            self._logger.error(f"Ошибка запуска визуализатора: {e}")
            self._running = False
            raise
    
    async def stop(self) -> None:
        """Останавливает визуализатор"""
        if not self._running:
            return
        
        try:
            self._running = False
            self._logger.info("Визуализатор остановлен")
        except Exception as e:
            self._logger.error(f"Ошибка остановки визуализатора: {e}")
    
    def is_running(self) -> bool:
        """Проверяет, запущен ли визуализатор"""
        return self._running
    
    def _run_server(self):
        """Запускает сервер в отдельном потоке"""
        try:
            # Дополнительно отключаем логи в потоке сервера
            with QuietFlaskServer():
                self._app.run(host=self._host, port=self._port, debug=False)
        except Exception as e:
            self._logger.error(f"Ошибка запуска сервера: {e}")
            self._running = False
    
    def _get_strategies_data(self) -> List[Dict[str, Any]]:
        """Получает данные о стратегиях"""
        try:
            # Если есть провайдер данных, получаем реальные данные
            if self._strategy_data_provider:
                strategies_data = self._strategy_data_provider.get_strategy_status()
                if strategies_data:
                    self._logger.info(f"✅ Получены данные о {len(strategies_data)} стратегиях")
                    return strategies_data
                else:
                    self._logger.info("⚠️ Нет данных о стратегиях от провайдера")
            else:
                self._logger.info("⚠️ Провайдер данных не инициализирован")
            
            # Если нет провайдера или нет данных, возвращаем пустой список
            self._logger.info("📝 Возвращаем пустой список стратегий")
            return []
        except Exception as e:
            self._logger.error(f"❌ Ошибка получения данных стратегий: {e}")
            return []
    
    def _get_current_session_info(self, market_data: dict, current_time) -> str:
        """
        Определяет информацию о текущей активной сессии
        
        Args:
            market_data: Данные от API
            current_time: Текущее время
            
        Returns:
            Строка с информацией о текущей сессии
        """
        try:
            # Если есть информация о следующей сессии и она текущая
            next_session = market_data.get('next_session')
            if next_session and next_session.get('is_current', False):
                session = next_session.get('session', {})
                session_name = session.get('name', 'Торговая сессия')
                session_start = next_session.get('start')
                session_end = next_session.get('end')
                
                if session_start and session_end:
                    if hasattr(session_start, 'strftime') and hasattr(session_end, 'strftime'):
                        return f"{session_name}: {session_start.strftime('%H:%M')} - {session_end.strftime('%H:%M')}"
                    else:
                        return f"{session_name}: {session_start} - {session_end}"
                elif session_start:
                    if hasattr(session_start, 'strftime'):
                        return f"{session_name}: {session_start.strftime('%H:%M')}"
                    else:
                        return f"{session_name}: {session_start}"
                else:
                    return f"Активна: {session_name}"
            
            # Если нет информации о текущей сессии, определяем по времени
            try:
                if hasattr(current_time, 'hour'):
                    current_hour = current_time.hour
                elif hasattr(current_time, 'strftime'):
                    # Если это строка времени, парсим ее
                    current_hour = int(current_time.strftime('%H'))
                else:
                    # Используем текущее время
                    current_hour = datetime.now().hour
                
                if 9 <= current_hour < 18:
                    result = "Основная сессия: 09:00 - 18:00"
                elif 18 <= current_hour < 23:
                    result = "Вечерняя сессия: 18:00 - 23:50"
                elif 23 <= current_hour or current_hour < 9:
                    result = "Ночная сессия: 23:50 - 09:00"
                else:
                    result = "Торговая сессия активна"
                
                return result
            except Exception as e:
                # Если не удалось определить время, возвращаем общую информацию
                self._logger.error(f"Ошибка определения времени: {e}")
                return "Торговая сессия активна"
            
            # Если нет информации о текущей сессии, возвращаем общую информацию
            return "Торговая сессия активна"
            
        except Exception as e:
            self._logger.error(f"Ошибка определения текущей сессии: {e}")
            return "Торговая сессия активна"
    
    def update_strategy_data_provider(self, session_controller) -> None:
        """
        Обновляет провайдер данных стратегий на реальный

        Args:
            session_controller: Контроллер торговой сессии
        """
        try:
            from visualization.interfaces import TradingSessionDataProvider

            # Создаем реальный провайдер данных
            real_provider = TradingSessionDataProvider(session_controller)
            self._strategy_data_provider = real_provider

            self._logger.info("✅ Провайдер данных стратегий обновлен на реальный")

        except Exception as e:
            self._logger.error(f"❌ Ошибка обновления провайдера данных: {e}")

        # Инициализация
        self._initialize_components()
