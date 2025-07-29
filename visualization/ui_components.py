#!/usr/bin/env python3
"""
Модуль для UI компонентов Dash
Создает интерфейс визуализации
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from dash import Dash, dcc, html, Input, Output, State, callback_context
from robotlib.utils.logger import get_logger

class UIComponents:
    """Компоненты пользовательского интерфейса"""
    
    def __init__(self, figi: str = "FUTIMOEXF000"):
        self.figi = figi
        self.logger = get_logger(__name__)
    
    def create_dash_app(self) -> Dash:
        """Создает Dash приложение"""
        app = Dash(__name__)
        
        # Стили
        app.index_string = self._get_custom_html_template()
        
        # Layout
        app.layout = self._create_layout()
        
        return app
    
    def _get_custom_html_template(self) -> str:
        """Возвращает кастомный HTML шаблон"""
        return '''
        <!DOCTYPE html>
        <html>
            <head>
                {%metas%}
                <title>{%title%}</title>
                {%favicon%}
                {%css%}
                <style>
                    body {
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        margin: 0;
                        padding: 20px;
                        min-height: 100vh;
                    }
                    .container {
                        max-width: 1400px;
                        margin: 0 auto;
                    }
                    .header {
                        text-align: center;
                        color: white;
                        margin-bottom: 30px;
                    }
                    .header h1 {
                        font-size: 2.5em;
                        margin: 0;
                        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
                    }
                    .controls {
                        display: flex;
                        gap: 15px;
                        justify-content: center;
                        margin-bottom: 30px;
                    }
                    .btn {
                        padding: 12px 24px;
                        border: none;
                        border-radius: 25px;
                        font-size: 16px;
                        font-weight: bold;
                        cursor: pointer;
                        transition: all 0.3s ease;
                        text-transform: uppercase;
                        letter-spacing: 1px;
                    }
                    .btn-start {
                        background: linear-gradient(45deg, #28a745, #20c997);
                        color: white;
                    }
                    .btn-stop {
                        background: linear-gradient(45deg, #dc3545, #e83e8c);
                        color: white;
                    }
                    .btn-reset {
                        background: linear-gradient(45deg, #ffc107, #fd7e14);
                        color: white;
                    }
                    .btn-test {
                        background: linear-gradient(45deg, #6f42c1, #e83e8c);
                        color: white;
                    }
                    .btn:hover {
                        transform: translateY(-2px);
                        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
                    }
                    .stats-grid {
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                        gap: 20px;
                        margin-bottom: 30px;
                    }
                    .stat-card {
                        background: rgba(255,255,255,0.95);
                        padding: 20px;
                        border-radius: 15px;
                        box-shadow: 0 8px 32px rgba(0,0,0,0.1);
                        text-align: center;
                    }
                    .price-display {
                        font-size: 3em;
                        font-weight: bold;
                        color: #2E86AB;
                        margin: 0;
                    }
                    .time-display {
                        font-size: 1.2em;
                        color: #A23B72;
                        margin: 5px 0;
                    }
                    .graph-container {
                        background: rgba(255,255,255,0.95);
                        padding: 20px;
                        border-radius: 15px;
                        box-shadow: 0 8px 32px rgba(0,0,0,0.1);
                        margin-bottom: 20px;
                    }
                    .signals-container {
                        background: rgba(255,255,255,0.95);
                        padding: 20px;
                        border-radius: 15px;
                        box-shadow: 0 8px 32px rgba(0,0,0,0.1);
                        max-height: 400px;
                        overflow-y: auto;
                    }
                    .signals-list {
                        flex: 1;
                        max-height: 300px;
                        overflow-y: auto;
                        padding-right: 10px;
                    }
                    .recent-signals {
                        flex: 1;
                        max-height: 300px;
                        overflow-y: auto;
                        padding-left: 10px;
                    }
                    /* Плавные переходы для уменьшения моргания при частых обновлениях */
                    .js-plotly-plot {
                        transition: opacity 0.1s ease-in-out;
                    }
                    .dash-graph {
                        transition: all 0.1s ease-in-out;
                    }
                    /* Плавное обновление текста */
                    h1, h2, h3, h4, p, div {
                        transition: color 0.05s ease-in-out;
                    }
                    /* Убираем резкие изменения */
                    * {
                        transition: background-color 0.05s ease-in-out;
                    }
                    /* Специально для цен - очень плавные переходы */
                    #current-price, #current-time, #market-status {
                        transition: all 0.05s ease-in-out;
                    }
                </style>
            </head>
            <body>
                {%app_entry%}
                <footer>
                    {%config%}
                    {%scripts%}
                    {%renderer%}
                </footer>
            </body>
        </html>
        '''
    
    def _create_layout(self) -> html.Div:
        """Создает layout приложения"""
        return html.Div([
            html.Div([
                html.H1("📈 Торговые сигналы от TradingSession", 
                       style={'color': 'white', 'textAlign': 'center', 'marginBottom': '10px'}),
                html.P(f"📊 Инструмент: {self.figi} | Фьючерс на индекс MOEX", 
                       style={'color': '#FFD700', 'textAlign': 'center', 'marginBottom': '5px', 'fontSize': '16px', 'fontWeight': 'bold'}),
                
                # Управление
                html.Div([
                    html.Button("🟢 Запустить", id="start-btn", className="btn btn-start"),
                    html.Button("🔴 Остановить", id="stop-btn", className="btn btn-stop"),
                    html.Button("🔄 Сбросить", id="reset-btn", className="btn btn-reset"),
                    html.Button("🧠 Умные данные", id="smart-data-btn", className="btn btn-start"),
                    html.Button("🧪 Тест на истории", id="history-test-btn", className="btn btn-test")
                ], className="controls"),
                
                # Интервал обновления
                dcc.Interval(
                    id='interval-component',
                    interval=1000,  # 1 секунда для обновления UI
                    n_intervals=0
                ),
                
                # Состояние симуляции
                dcc.Store(id='simulation-state', data={'running': False}),
                
                # Основная статистика
                self._create_stats_grid(),
                
                # График
                self._create_graph_container(),
                
                # Сигналы
                self._create_signals_container()
                
            ], className="container")
        ])
    
    def _create_stats_grid(self) -> html.Div:
        """Создает сетку статистики"""
        return html.Div([
            # Текущая цена
            html.Div([
                html.H2("💰 Текущая цена", style={'color': '#2E86AB', 'marginBottom': '10px'}),
                html.H1(id="current-price", children="2923.5 ₽", 
                       className="price-display")
            ], className="stat-card"),
            
            # Статус рынка
            html.Div([
                html.H3("📊 Статус рынка", style={'color': '#2E86AB', 'marginBottom': '15px'}),
                html.H2(id="market-status", children="🟡 Инициализация", 
                       style={'color': '#F18F01', 'margin': '0'})
            ], className="stat-card"),
            
            # Статистика сигналов
            html.Div([
                html.H3("📈 Статистика сигналов", style={'color': '#2E86AB', 'marginBottom': '15px'}),
                html.Div([
                    html.Div([
                        html.H4("🟢 Покупки", style={'margin': '0', 'color': '#666'}),
                        html.H2(id="buy-count", children="0", 
                               style={'margin': '0', 'color': '#28a745'})
                    ], style={'textAlign': 'center', 'flex': '1'}),
                    
                    html.Div([
                        html.H4("🔴 Продажи", style={'margin': '0', 'color': '#666'}),
                        html.H2(id="sell-count", children="0", 
                               style={'margin': '0', 'color': '#dc3545'})
                    ], style={'textAlign': 'center', 'flex': '1'}),
                    
                    html.Div([
                        html.H4("📊 Всего", style={'margin': '0', 'color': '#666'}),
                        html.H2(id="total-signals", children="0", 
                               style={'margin': '0', 'color': '#2E86AB'})
                    ], style={'textAlign': 'center', 'flex': '1'})
                ], style={'display': 'flex', 'gap': '15px'})
            ], className="stat-card"),
            
            # Статистика ордеров
            html.Div([
                html.H3("🎯 Статистика ордеров", style={'color': '#2E86AB', 'marginBottom': '15px'}),
                html.Div([
                    html.Div([
                        html.H4("📋 Всего ордеров", style={'margin': '0', 'color': '#666'}),
                        html.H2(id="orders-count", children="0", 
                               style={'margin': '0', 'color': '#6f42c1'})
                    ], style={'textAlign': 'center', 'flex': '1'}),
                    
                    html.Div([
                        html.H4("💰 Объем", style={'margin': '0', 'color': '#666'}),
                        html.H2(id="total-volume", children="0", 
                               style={'margin': '0', 'color': '#fd7e14'})
                    ], style={'textAlign': 'center', 'flex': '1'})
                ], style={'display': 'flex', 'gap': '15px'})
            ], className="stat-card"),
            
            # Статус стратегий
            html.Div([
                html.H3("🎯 Статус стратегий", style={'color': '#2E86AB', 'marginBottom': '15px'}),
                html.Div(id="strategy-status", children="Загрузка статуса стратегий...")
            ], className="stat-card"),
            
            # Торговый статус
            html.Div([
                html.H3("🕐 Торговый статус", style={'color': '#2E86AB', 'marginBottom': '15px'}),
                html.Div(id="trading-status", children="Загрузка торгового статуса...")
            ], className="stat-card")
        ], className="stats-grid")
    
    def _create_graph_container(self) -> html.Div:
        """Создает контейнер для графика"""
        return html.Div([
            html.H3("📊 График цен", style={'color': '#2E86AB', 'marginBottom': '15px'}),
            dcc.Graph(id='trading-graph')
        ], className="graph-container")
    
    def _create_signals_container(self) -> html.Div:
        """Создает контейнер для сигналов"""
        return html.Div([
            html.H3("🎯 Торговые сигналы", style={'color': '#2E86AB', 'marginBottom': '15px'}),
            html.Div([
                html.Div(id="signals-list", className="signals-list"),
                html.Div([
                    html.H4("📋 Последние сигналы", style={'color': '#2E86AB', 'marginBottom': '10px'}),
                    html.Div(id="recent-signals", children="Ожидание сигналов...")
                ], className="recent-signals")
            ], style={'display': 'flex', 'gap': '20px'})
        ], className="signals-container")
    
    def create_signals_list(self, signals_data: List[Dict[str, Any]]) -> List[html.Div]:
        """Создает список сигналов"""
        signals_list = []
        if signals_data:
            for signal in signals_data[-10:]:  # Последние 10 сигналов
                signal_color = '#28a745' if signal['type'] == 'buy' else '#dc3545'
                signals_list.append(
                    html.Div([
                        html.Span(signal['time'].strftime("%H:%M:%S"), 
                                 style={'color': '#666', 'fontSize': '0.9em'}),
                        html.Br(),
                        html.Span(f"{signal['price']:.2f} ₽", 
                                 style={'color': '#2E86AB', 'fontWeight': 'bold'}),
                        html.Span(f" {signal['type'].upper()}", 
                                 style={'color': signal_color, 'fontWeight': 'bold', 'marginLeft': '10px'}),
                        html.Br(),
                        html.Span(signal.get('reason', ''), 
                                 style={'color': '#999', 'fontSize': '0.8em'})
                    ], style={'padding': '5px', 'borderBottom': '1px solid #eee'})
                )
        else:
            signals_list = [html.P("Ожидание сигналов...", style={'color': '#666'})]
        
        return signals_list
    
    def create_recent_signals(self, signals_data: List[Dict[str, Any]]) -> List[html.Div]:
        """Создает список последних сигналов с подробной информацией"""
        recent_signals = []
        if signals_data:
            for signal in signals_data[-5:]:  # Последние 5 сигналов
                signal_color = '#00ff88' if signal['type'] == 'buy' else '#ff4444'
                signal_icon = '🟢' if signal['type'] == 'buy' else '🔴'
                
                recent_signals.append(
                    html.Div([
                        html.Div([
                            html.Span(signal_icon, style={'fontSize': '1.2em', 'marginRight': '8px'}),
                            html.Span(signal['type'].upper(), 
                                     style={'color': signal_color, 'fontWeight': 'bold', 'fontSize': '0.9em'})
                        ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '5px'}),
                        
                        html.Div([
                            html.Span(f"Цена: {signal['price']:.2f} ₽", 
                                     style={'color': '#2E86AB', 'fontSize': '0.8em'}),
                            html.Br(),
                            html.Span(f"Время: {signal['time'].strftime('%H:%M:%S')}", 
                                     style={'color': '#666', 'fontSize': '0.7em'}),
                            html.Br(),
                            html.Span(f"Причина: {signal.get('reason', 'N/A')}", 
                                     style={'color': '#999', 'fontSize': '0.7em'}),
                            html.Br() if 'quantity' in signal else '',
                            html.Span(f"Количество: {signal.get('quantity', 'N/A')}", 
                                     style={'color': '#999', 'fontSize': '0.7em'}) if 'quantity' in signal else '',
                            html.Br() if 'strategy' in signal else '',
                            html.Span(f"Стратегия: {signal.get('strategy', 'N/A')}", 
                                     style={'color': '#999', 'fontSize': '0.7em'}) if 'strategy' in signal else ''
                        ])
                    ], style={
                        'padding': '8px', 
                        'marginBottom': '8px', 
                        'border': f'1px solid {signal_color}',
                        'borderRadius': '5px',
                        'backgroundColor': f'{signal_color}10'
                    })
                )
        else:
            recent_signals = [html.P("Ожидание сигналов...", style={'color': '#666'})]
        
        return recent_signals
