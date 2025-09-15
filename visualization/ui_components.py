#!/usr/bin/env python3
"""
Модуль для UI компонентов Dash
Создает интерфейс визуализации
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from dash import Dash, dcc, html, Input, Output, State, callback_context
from dash_extensions import WebSocket
from robotlib.utils.logger import get_logger
from visualization.logging_config import disable_verbose_logging

class UIComponents:
    """Компоненты пользовательского интерфейса"""
    
    def __init__(self, figi: str = "FUTIMOEXF000", chart_builder=None):
        self.figi = figi
        self.logger = get_logger(__name__)
        self._chart_builder = chart_builder
        
        # Отключаем избыточные логи
        self._disable_verbose_logging()
    
    def _disable_verbose_logging(self):
        """Отключает избыточные логи Flask/Dash"""
        disable_verbose_logging(enable_debug_logs=True)
    
    def create_dash_app(self) -> Dash:
        """Создает Dash приложение"""
        app = Dash(__name__)
        
        # Стили
        app.index_string = self._get_custom_html_template()
        
        # Layout
        app.layout = self._create_layout()
        
        return app
    
    def _get_custom_html_template(self) -> str:
        """Возвращает кастомный HTML шаблон с подключением CSS"""
        return '''
        <!DOCTYPE html>
        <html>
            <head>
                {%metas%}
                <title>{%title%}</title>
                <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📈</text></svg>">
                {%css%}
                <link rel="stylesheet" href="/assets/styles.css">
            </head>
            <body>
                <div class="container">
                    <div id="main-content">
                        <!-- Контент будет заменен Dash -->
                    </div>
                </div>
                {%app_entry%}
                <footer>
                    {%config%}
                    {%scripts%}
                    {%renderer%}
                </footer>
            </body>
        </html>
        '''
    
    def _create_header(self) -> html.Div:
        """Создает заголовок дашборда"""
        return html.Div([
            html.H1("Фьючерс на индекс MOEX", className="header-title"),
            html.Div([
                html.Span("Текущая цена:", style={'marginRight': '8px'}),
                html.Span(id="current-price", children="—", className="stat-value")
            ], style={'marginTop': '6px'})
        ], className="header")
    
    def _create_market_status(self) -> html.Div:
        """Создает блок статуса рынка"""
        return html.Div([
            html.H3("📊 Статус рынка", className="market-status-title"),
            html.Div([
                html.Span(id="market-status", children="—"),
                html.Br(),
                html.Span(id="market-time", children="—")
            ], id="market-status-content")
        ], className="market-status")
    
    def _create_statistics_cards(self) -> html.Div:
        """Создает карточки статистики"""
        return html.Div([
            # Секция сигналов
            html.Div([
                html.H3("📊 СИГНАЛЫ", className="section-title"),
                html.Div([
                    html.Div([
                        html.H4("📈 Сигналы BUY", className="stat-title"),
                        html.H2(id="buy-signals-count", children="0", 
                               className="stat-value", style={'color': '#28a745'})
                    ], style={'textAlign': 'center', 'flex': '1'}),
                    html.Div([
                        html.H4("📉 Сигналы SELL", className="stat-title"),
                        html.H2(id="sell-signals-count", children="0", 
                               className="stat-value", style={'color': '#dc3545'})
                    ], style={'textAlign': 'center', 'flex': '1'})
                ], style={'display': 'flex', 'gap': '20px', 'marginTop': '8px'})
            ], className="signals-section"),
            
            # Секция ордеров
            html.Div([
                html.H3("📋 ОРДЕРЫ", className="section-title"),
                html.Div([
                    html.Div([
                        html.H4("📈 Ордеры BUY", className="stat-title"),
                        html.H2(id="buy-orders-count", children="0", 
                               className="stat-value", style={'color': '#28a745'})
                    ], style={'textAlign': 'center', 'flex': '1'}),
                    html.Div([
                        html.H4("📉 Ордеры SELL", className="stat-title"),
                        html.H2(id="sell-orders-count", children="0", 
                               className="stat-value", style={'color': '#dc3545'})
                    ], style={'textAlign': 'center', 'flex': '1'})
                ], style={'display': 'flex', 'gap': '20px', 'marginTop': '8px'})
            ], className="orders-section"),
            
            # Секция стратегий
            html.Div([
                html.H3("🎯 СТРАТЕГИИ", className="section-title"),
                html.Div([
                    html.Div([
                        html.H4("📊 Статус стратегий", className="stat-title"),
                        html.H2(id="strategy-status", children="Активны", 
                               className="stat-value", style={'color': '#28a745'})
                    ], style={'textAlign': 'center', 'flex': '1'}),
                    html.Div([
                        html.H4("⚡ Торговля", className="stat-title"),
                        html.H2(id="trading-status", children="Включена", 
                               className="stat-value", style={'color': '#28a745'})
                    ], style={'textAlign': 'center', 'flex': '1'})
                ], style={'display': 'flex', 'gap': '20px', 'marginTop': '8px'})
            ], className="strategies-section")
        ], className="stats-grid")
    
    def _create_chart_section(self) -> html.Div:
        """Создает секцию с графиком"""
        # Создаем пустой график если chart_builder не передан
        if self._chart_builder:
            figure = self._chart_builder.create_trading_chart([], [], [], 0.0)
        else:
            # Создаем пустой график вручную
            import plotly.graph_objects as go
            figure = go.Figure()
            figure.update_layout(
                title="Торговый график",
                xaxis_title="Время",
                yaxis_title="Цена",
                template="plotly_white"
            )
        
        return html.Div([
            html.H3("📈 Торговый график", className="chart-title"),
            html.Div([
                dcc.Checklist(
                    id="toggle-rangebreaks",
                    options=[{"label": "Скрывать неактивное время", "value": "hide"}],
                    value=["hide"],
                    inputStyle={"marginRight": "6px"},
                    labelStyle={"marginRight": "16px"},
                    style={"marginBottom": "6px"}
                )
            ]),
            dcc.Graph(
                id="trading-graph",
                figure=figure,
                config={'displayModeBar': True, 'displaylogo': False}
            )
        ], className="chart-container")
    
    def _create_signals_section(self) -> html.Div:
        """Создает секцию с сигналами"""
        return html.Div([
            html.H3("📋 Последние сигналы", className="signals-title"),
            html.Div(id="signals-list", children=[], className="signals-list"),
            html.Div(id="recent-signals", children=[], className="signals-list")
        ], className="signals-container")
    
    def _create_portfolio_section(self) -> html.Div:
        """Создает секцию портфеля"""
        return html.Div([
            html.H3("💰 Портфель", className="portfolio-title"),
            html.Div([
                html.Div([
                    html.Div([
                        html.H4("💰 Баланс", className="portfolio-label"),
                        html.H2(id="portfolio-balance", children="0", className="portfolio-value")
                    ], className="portfolio-item"),
                    html.Div([
                        html.H4("📊 P&L", className="portfolio-label"),
                        html.H2(id="portfolio-pnl", children="0", className="portfolio-value")
                    ], className="portfolio-item")
                ], className="portfolio-row"),
                html.Div([
                    html.Div([
                        html.H4("📈 Вариационная маржа", className="portfolio-label"),
                        html.H2(id="portfolio-variation-margin", children="0", className="portfolio-value")
                    ], className="portfolio-item"),
                    html.Div([
                        html.H4("🛡️ Гарантийное обеспечение", className="portfolio-label"),
                        html.H2(id="portfolio-guarantee-deposit", children="0", className="portfolio-value")
                    ], className="portfolio-item")
                ], className="portfolio-row")
            ], className="portfolio-grid")
        ], className="portfolio-container")
    
    def _create_layout(self) -> html.Div:
        """Создает layout приложения используя Dash компоненты"""
        return html.Div([
            # WebSocket клиент для push-уведомлений (polling отключен)
            WebSocket(id="ws", url="/ws"),
            
            # Состояние симуляции
            dcc.Store(id='simulation-state', data={'running': False}),
            
            # Основные компоненты
            self._create_header(),
            self._create_market_status(),
            self._create_statistics_cards(),
            self._create_chart_section(),
            self._create_signals_section(),
            self._create_portfolio_section()
        ])
    
    
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
                        html.Span(f"{signal.get('price', 0):.2f} ₽", 
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
                            html.Span(f"Цена: {signal.get('price', 0):.2f} ₽", 
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
