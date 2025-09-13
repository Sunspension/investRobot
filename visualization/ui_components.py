#!/usr/bin/env python3
"""
Модуль для UI компонентов Dash
Создает интерфейс визуализации
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from dash import Dash, dcc, html, Input, Output, State, callback_context
from robotlib.utils.logger import get_logger
from visualization.logging_config import disable_verbose_logging

class UIComponents:
    """Компоненты пользовательского интерфейса"""
    
    def __init__(self, figi: str = "FUTIMOEXF000"):
        self.figi = figi
        self.logger = get_logger(__name__)
        
        # Отключаем избыточные логи
        self._disable_verbose_logging()
    
    def _disable_verbose_logging(self):
        """Отключает избыточные логи Flask/Dash"""
        disable_verbose_logging()
    
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
                <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📈</text></svg>">
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
                        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
                        gap: 24px;
                        margin-bottom: 30px;
                    }
                    .stat-card {
                        background: rgba(255,255,255,0.98);
                        padding: 24px;
                        border-radius: 20px;
                        box-shadow: 0 12px 40px rgba(0,0,0,0.08);
                        text-align: center;
                        border: 1px solid rgba(255,255,255,0.2);
                        backdrop-filter: blur(10px);
                        transition: all 0.3s ease;
                        min-height: 180px;
                        display: flex;
                        flex-direction: column;
                        justify-content: flex-start;
                    }
                    .portfolio-card {
                        min-height: 200px;
                    }
                    .portfolio-row {
                        display: flex;
                        gap: 20px;
                        margin-bottom: 16px;
                    }
                    .portfolio-row:last-child {
                        margin-bottom: 0;
                    }
                    .portfolio-item {
                        text-align: center;
                        flex: 1;
                        padding: 8px;
                        border-radius: 12px;
                        background: rgba(248, 249, 250, 0.8);
                        transition: all 0.2s ease;
                    }
                    .portfolio-item:hover {
                        background: rgba(248, 249, 250, 1);
                        transform: translateY(-2px);
                    }
                    .stat-card:hover {
                        transform: translateY(-4px);
                        box-shadow: 0 16px 50px rgba(0,0,0,0.12);
                    }
                    .price-display {
                        font-size: 2.8em;
                        font-weight: 700;
                        color: #2E86AB;
                        margin: 0;
                        line-height: 1.1;
                        text-shadow: 0 2px 4px rgba(46, 134, 171, 0.2);
                    }
                    .time-display {
                        font-size: 1.1em;
                        color: #A23B72;
                        margin: 8px 0;
                        font-weight: 500;
                    }
                    .card-title {
                        font-size: 1.1em;
                        font-weight: 600;
                        color: #2E86AB;
                        margin: 0 0 20px 0;
                        text-align: center;
                        letter-spacing: 0.5px;
                        text-transform: uppercase;
                        padding-top: 8px;
                    }
                    .card-value {
                        font-size: 1.8em;
                        font-weight: 700;
                        margin: 8px 0;
                        line-height: 1.2;
                    }
                    .card-subtitle {
                        font-size: 0.9em;
                        color: #666;
                        margin: 4px 0;
                        font-weight: 500;
                    }
                    .emoji-text {
                        display: inline-flex;
                        align-items: center;
                        justify-content: center;
                        gap: 6px;
                    }
                    .emoji-text .emoji {
                        font-size: 1.1em;
                        line-height: 1;
                    }
                    .emoji-text .text {
                        font-size: 0.95em;
                        line-height: 1.2;
                    }
                    .graph-container {
                        background: rgba(255,255,255,0.98);
                        padding: 24px;
                        border-radius: 20px;
                        box-shadow: 0 12px 40px rgba(0,0,0,0.08);
                        margin-bottom: 24px;
                        border: 1px solid rgba(255,255,255,0.2);
                        backdrop-filter: blur(10px);
                        display: flex;
                        flex-direction: column;
                        justify-content: flex-start;
                    }
                    .signals-container {
                        background: rgba(255,255,255,0.98);
                        padding: 24px;
                        border-radius: 20px;
                        box-shadow: 0 12px 40px rgba(0,0,0,0.08);
                        max-height: 400px;
                        overflow-y: auto;
                        border: 1px solid rgba(255,255,255,0.2);
                        backdrop-filter: blur(10px);
                        display: flex;
                        flex-direction: column;
                        justify-content: flex-start;
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
                        transition: opacity 0.3s ease-in-out;
                    }
                    .dash-graph {
                        transition: all 0.3s ease-in-out;
                    }
                    /* Плавное обновление текста */
                    h1, h2, h3, h4, p, div {
                        transition: color 0.2s ease-in-out;
                    }
                    /* Убираем резкие изменения */
                    * {
                        transition: background-color 0.2s ease-in-out;
                    }
                    /* Специально для цен - очень плавные переходы */
                    #current-price, #current-time, #market-status {
                        transition: all 0.2s ease-in-out;
                    }
                    /* Убираем моргание при обновлении */
                    .dash-spinner {
                        display: none !important;
                    }
                    /* Отключаем все индикаторы загрузки */
                    .dash-loading {
                        display: none !important;
                    }
                    .dash-loading--children {
                        display: none !important;
                    }
                    /* Убираем анимации загрузки */
                    ._dash-loading {
                        display: none !important;
                    }
                    /* Отключаем моргание favicon */
                    link[rel="icon"] {
                        display: none !important;
                    }
                    /* Плавные переходы для всех элементов */
                    .stat-card, .graph-container, .signals-container {
                        transition: all 0.2s ease-in-out;
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
                    html.Button("🔴 Остановить", id="stop-btn", className="btn btn-stop")
                ], className="controls"),
                
                # Интервал обновления - редкие обновления каждые 60 секунд
                dcc.Interval(
                    id='interval-component',
                    interval=60000,  # 60 секунд для обновления UI (редко, без моргания)
                    n_intervals=0,
                    disabled=False
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
                html.H3("💰 Текущая цена", className="card-title"),
                html.H1(id="current-price", children="2923.5 ₽", 
                       className="price-display")
            ], className="stat-card"),
            
            # Статус рынка
            html.Div([
                html.H3("📊 Статус рынка", className="card-title"),
                html.Div([
                    html.H2(id="market-status", children="🔄 Загрузка...", 
                           className="card-value", style={'color': '#F18F01', 'fontSize': '1.2em'})
                ], style={'textAlign': 'center'})
            ], className="stat-card"),
            
            # Статистика сигналов
            html.Div([
                html.H3("📈 Статистика сигналов", className="card-title"),
                html.Div([
                    html.Div([
                        html.H4("🟢 Покупки", className="card-subtitle"),
                        html.H2(id="buy-count", children="0", 
                               className="card-value", style={'color': '#28a745'})
                    ], style={'textAlign': 'center', 'flex': '1'}),
                    
                    html.Div([
                        html.H4("🔴 Продажи", className="card-subtitle"),
                        html.H2(id="sell-count", children="0", 
                               className="card-value", style={'color': '#dc3545'})
                    ], style={'textAlign': 'center', 'flex': '1'})
                ], style={'display': 'flex', 'gap': '20px', 'marginTop': '8px'})
            ], className="stat-card"),
            
            # Статистика ордеров
            html.Div([
                html.H3("🎯 Статистика ордеров", className="card-title"),
                html.Div([
                    html.Div([
                        html.H4("📋 Всего ордеров", className="card-subtitle"),
                        html.H2(id="orders-count", children="0", 
                               className="card-value", style={'color': '#6f42c1'})
                    ], style={'textAlign': 'center', 'flex': '1'}),
                    
                    html.Div([
                        html.H4("💰 Объем", className="card-subtitle"),
                        html.H2(id="total-volume", children="0", 
                               className="card-value", style={'color': '#fd7e14'})
                    ], style={'textAlign': 'center', 'flex': '1'})
                ], style={'display': 'flex', 'gap': '20px', 'marginTop': '8px'})
            ], className="stat-card"),
            
            # Портфель
            self._create_portfolio_card(),
            
            # Статус стратегий
            html.Div([
                html.H3("🎯 Статус стратегий", className="card-title"),
                html.Div(id="strategy-status", children="Загрузка статуса стратегий...", 
                        className="card-value", style={'fontSize': '1em', 'color': '#666'})
            ], className="stat-card"),
            
            # Торговый статус
            html.Div([
                html.H3("🕐 Торговый статус", className="card-title"),
                html.Div(id="trading-status", children="Загрузка торгового статуса...", 
                        className="card-value", style={'fontSize': '1em', 'color': '#666'})
            ], className="stat-card")
        ], className="stats-grid")
    
    def _create_graph_container(self) -> html.Div:
        """Создает контейнер для графика"""
        return html.Div([
            html.H3("📊 График цен", className="card-title"),
            dcc.Graph(id='trading-graph')
        ], className="graph-container")
    
    def _create_signals_container(self) -> html.Div:
        """Создает контейнер для сигналов"""
        return html.Div([
            html.H3("🎯 Торговые сигналы", className="card-title"),
            html.Div([
                html.Div(id="signals-list", className="signals-list"),
                html.Div([
                    html.H4("📋 Последние сигналы", className="card-subtitle", style={'marginBottom': '12px'}),
                    html.Div(id="recent-signals", children="Ожидание сигналов...")
                ], className="recent-signals")
            ], style={'display': 'flex', 'gap': '24px'})
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
    
    def _create_portfolio_card(self) -> html.Div:
        """Создает карточку портфеля"""
        return html.Div([
            html.H3("💼 Портфель", className="card-title"),
            html.Div([
                # Первая строка - Баланс и P&L
                html.Div([
                    html.Div([
                        html.H4("💰 Баланс", className="card-subtitle"),
                        html.H2(id="portfolio-balance", children="0.00 ₽", 
                               className="card-value", style={'color': '#28a745'})
                    ], className="portfolio-item"),
                    
                    html.Div([
                        html.H4("📈 P&L", className="card-subtitle"),
                        html.H2(id="portfolio-pnl", children="0.00 ₽", 
                               className="card-value")
                    ], className="portfolio-item")
                ], className="portfolio-row"),
                
                # Вторая строка - Вариационная маржа и ГО
                html.Div([
                    html.Div([
                        html.H4("📊 Вар. маржа", className="card-subtitle"),
                        html.H2(id="portfolio-variation-margin", children="0.00 ₽", 
                               className="card-value")
                    ], className="portfolio-item"),
                    
                    html.Div([
                        html.H4("🛡️ ГО", className="card-subtitle"),
                        html.H2(id="portfolio-guarantee-deposit", children="0.00 ₽", 
                               className="card-value", style={'color': '#ffc107'})
                    ], className="portfolio-item")
                ], className="portfolio-row")
            ], style={'marginTop': '8px'})
        ], className="stat-card portfolio-card")
