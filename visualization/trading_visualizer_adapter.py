"""
Адаптер для интеграции TradingSignalsVisualizer с торговой системой
"""
import asyncio
import threading
from typing import Dict, Any, Optional
from datetime import datetime
from robotlib.utils.logger import get_logger
from robotlib.trading.visualizer_interface import TradingVisualizerable

# Импортируем компоненты визуализатора
from visualization.data_manager import DataManager
from visualization.chart_builder import ChartBuilder
from visualization.ui_components import UIComponents
from visualization.trading_session_manager import TradingSessionManager


class TradingVisualizerAdapter(TradingVisualizerable):
    """Адаптер для интеграции TradingSignalsVisualizer с торговой системой"""
    
    def __init__(
        self, 
        figi: str = "FUTIMOEXF000",
        update_interval: int = 1,
        host: str = "127.0.0.1",
        port: int = 8050
    ):
        """
        Инициализация адаптера визуализатора
        
        Args:
            figi: FIGI инструмента
            update_interval: Интервал обновления в секундах
            host: Хост для веб-интерфейса
            port: Порт для веб-интерфейса
        """
        self.figi = figi
        self.update_interval = update_interval
        self.host = host
        self.port = port
        self.logger = get_logger(__name__)
        
        # Состояние
        self.running = False
        self.app = None
        self.server_thread = None
        
        # Компоненты визуализатора
        self.data_manager = DataManager()
        self.chart_builder = ChartBuilder()
        self.ui_components = UIComponents(figi)
        self.trading_session_manager = None
        
        # Инициализация
        self._initialize_components()
    
    def _initialize_components(self):
        """Инициализирует компоненты визуализатора"""
        try:
            # Создаем Dash приложение
            self.app = self._create_dash_app()
            self.logger.info("Компоненты визуализатора инициализированы")
        except Exception as e:
            self.logger.error(f"Ошибка инициализации компонентов: {e}")
            raise
    
    def _create_dash_app(self):
        """Создает Dash приложение"""
        from dash import Dash, dcc, html, Input, Output, State, callback_context
        
        app = Dash(__name__)
        
        # Стили
        app.index_string = self.ui_components._get_custom_html_template()
        
        # Layout
        app.layout = self.ui_components._create_layout()
        
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
             Input('reset-btn', 'n_clicks')],
            [State('simulation-state', 'data')]
        )
        def control_simulation(start_clicks, stop_clicks, reset_clicks, state):
            ctx = callback_context
            if not ctx.triggered:
                return state
            
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            
            if button_id == 'start-btn':
                state['running'] = True
            elif button_id == 'stop-btn':
                state['running'] = False
            elif button_id == 'reset-btn':
                state['running'] = False
                self.data_manager.reset_data()
            
            return state
        
        return app
    
    def _update_display(self):
        """Обновляет отображение данных"""
        try:
            # Получаем снимок данных
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
            from dash import html
            from plotly.graph_objects import Figure
            return (Figure(), "Ошибка", "❌ Ошибка", "0", "0", "0", "0", "0",
                   [html.P("Ошибка отображения")], [html.P("Ошибка отображения")], [html.P("Ошибка отображения")], [html.P("Ошибка отображения")])
    
    def _get_strategy_status(self):
        """Получает статус стратегий"""
        from dash import html
        return [html.P("Стратегии не инициализированы", style={'color': '#666'})]
    
    def _get_trading_status(self):
        """Получает торговый статус"""
        from dash import html
        return [html.P("Торговый статус недоступен", style={'color': '#666'})]
    
    def _get_market_status_info(self):
        """Получает информацию о состоянии рынка"""
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
    
    async def add_candle(self, candle_data: Dict[str, Any]) -> None:
        """Добавляет свечу в визуализатор"""
        try:
            self.data_manager.add_candle(candle_data)
            self.logger.debug(f"Добавлена свеча: {candle_data.get('time', 'N/A')}")
        except Exception as e:
            self.logger.error(f"Ошибка добавления свечи: {e}")
    
    async def add_signal(self, signal_data: Dict[str, Any]) -> None:
        """Добавляет торговый сигнал в визуализатор"""
        try:
            self.data_manager.add_signal(signal_data)
            self.logger.debug(f"Добавлен сигнал: {signal_data.get('type', 'N/A')} по цене {signal_data.get('price', 'N/A')}")
        except Exception as e:
            self.logger.error(f"Ошибка добавления сигнала: {e}")
    
    async def add_order(self, order_data: Dict[str, Any]) -> None:
        """Добавляет ордер в визуализатор"""
        try:
            self.data_manager.add_order(order_data)
            self.logger.debug(f"Добавлен ордер: {order_data.get('type', 'N/A')} по цене {order_data.get('price', 'N/A')}")
        except Exception as e:
            self.logger.error(f"Ошибка добавления ордера: {e}")
    
    async def update_portfolio(self, portfolio_data: Dict[str, Any]) -> None:
        """Обновляет информацию о портфеле в визуализаторе"""
        try:
            # Здесь можно добавить логику обновления портфеля
            self.logger.debug(f"Обновлен портфель: {portfolio_data}")
        except Exception as e:
            self.logger.error(f"Ошибка обновления портфеля: {e}")
    
    async def update_market_status(self, status_data: Dict[str, Any]) -> None:
        """Обновляет статус рынка в визуализаторе"""
        try:
            # Здесь можно добавить логику обновления статуса рынка
            self.logger.debug(f"Обновлен статус рынка: {status_data}")
        except Exception as e:
            self.logger.error(f"Ошибка обновления статуса рынка: {e}")
    
    async def start(self) -> None:
        """Запускает визуализатор"""
        if self.running:
            self.logger.warning("Визуализатор уже запущен")
            return
        
        try:
            self.running = True
            
            # Запускаем сервер в отдельном потоке
            self.server_thread = threading.Thread(
                target=self._run_server, 
                daemon=True
            )
            self.server_thread.start()
            
            self.logger.info(f"Визуализатор запущен на http://{self.host}:{self.port}")
            
        except Exception as e:
            self.logger.error(f"Ошибка запуска визуализатора: {e}")
            self.running = False
            raise
    
    async def stop(self) -> None:
        """Останавливает визуализатор"""
        if not self.running:
            return
        
        try:
            self.running = False
            self.logger.info("Визуализатор остановлен")
        except Exception as e:
            self.logger.error(f"Ошибка остановки визуализатора: {e}")
    
    def is_running(self) -> bool:
        """Проверяет, запущен ли визуализатор"""
        return self.running
    
    def _run_server(self):
        """Запускает сервер в отдельном потоке"""
        try:
            self.app.run(host=self.host, port=self.port, debug=False)
        except Exception as e:
            self.logger.error(f"Ошибка запуска сервера: {e}")
            self.running = False
