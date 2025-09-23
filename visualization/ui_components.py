#!/usr/bin/env python3
"""
Модуль для UI компонентов Dash
Создает интерфейс визуализации
"""

from typing import List, Dict, Any
from dash import Dash, dcc, html
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
                html.Span("Текущая цена:", style={'marginRight': '8px', 'fontSize': '24px'}),
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
            html.Div([
                # Секция сигналов
                html.Div([
                    html.Div([
                        html.H3("СИГНАЛЫ", className="section-title"),
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
                    ], style={'textAlign': 'center', 'flex': '1'}),
                ], className="signals-section"),
                # Секция ордеров
                html.Div([
                    html.Div([
                        html.H3("ОРДЕРЫ", className="section-title"),
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
                        ], style={'display': 'flex', 'gap': '20px', 'marginTop': '8px'}),
                    ], style={'textAlign': 'center', 'flex': '1'}),
                ], className="orders-section"),
            ], className="container-grid")
        ], className="stats-grid")
    
    def _create_chart_section(self) -> html.Div:
        """Создает секцию с графиком"""
        # Создаем пустой график если chart_builder не передан
        if self._chart_builder:
            # В ChartBuilder внутри включим скрытие разрывов по умолчанию
            figure = self._chart_builder.create_trading_chart([], [], 0.0, hide_inactive_time=True)
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
    
    def _create_orders_section(self) -> html.Div:
        """Создает секцию с ордерами"""
        return html.Div([
            html.H3("🧾 Последние ордера", className="orders-title"),
            html.Div(id="orders-list", children=[], className="orders-list"),
            html.Div(id="recent-orders", children=[], className="orders-list")
        ], className="orders-container")
    
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
            WebSocket(id="ws_events", url="/ws"),
            
            # Основные компоненты
            self._create_header(),
            self._create_market_status(),
            self._create_statistics_cards(),
            self._create_chart_section(),
            self._create_orders_section(),
            self._create_portfolio_section()
        ])
    
    
    # Удалены списки сигналов из UI по требованию
    
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
    
    def create_orders_list(self, orders_data: List[Dict[str, Any]]) -> List[html.Div]:
        """Создает компактный список ордеров"""
        items: List[html.Div] = []
        if orders_data:
            for order in orders_data[-10:]:
                order_type = str(order.get('type', 'N/A')).upper()
                is_buy = order.get('type') in ['buy', 'short_buy', 'stop_loss_short_cover']
                order_color = '#28a745' if is_buy else '#dc3545'
                t = order.get('time')
                time_text = t.strftime('%H:%M:%S') if hasattr(t, 'strftime') else str(t)
                items.append(
                    html.Div([
                        html.Span(time_text, style={'color': '#666', 'fontSize': '0.9em'}),
                        html.Br(),
                        html.Span(f"{float(order.get('price', 0.0)):.2f} ₽", style={'color': '#2E86AB', 'fontWeight': 'bold'}),
                        html.Span(f" {order_type}", style={'color': order_color, 'fontWeight': 'bold', 'marginLeft': '10px'})
                    ], style={'padding': '5px', 'borderBottom': '1px solid #eee'})
                )
        else:
            items = []
        return items
    
    def create_recent_orders(self, orders_data: List[Dict[str, Any]]) -> List[html.Div]:
        """Создает подробный список последних ордеров"""
        blocks: List[html.Div] = []
        if orders_data:
            for order in orders_data[-5:]:
                is_buy = order.get('type') in ['buy', 'short_buy', 'stop_loss_short_cover']
                color = '#00ff88' if is_buy else '#ff4444'
                icon = '🟢' if is_buy else '🔴'
                t = order.get('time')
                time_text = t.strftime('%H:%M:%S') if hasattr(t, 'strftime') else str(t)
                blocks.append(
                    html.Div([
                        html.Div([
                            html.Span(icon, style={'fontSize': '1.2em', 'marginRight': '8px'}),
                            html.Span(str(order.get('type', 'N/A')).upper(), style={'color': color, 'fontWeight': 'bold', 'fontSize': '0.9em'})
                        ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '5px'}),
                        html.Div([
                            html.Span(f"Цена: {float(order.get('price', 0.0)):.2f} ₽", style={'color': '#2E86AB', 'fontSize': '0.8em'}),
                            html.Br(),
                            html.Span(f"Время: {time_text}", style={'color': '#666', 'fontSize': '0.7em'}),
                            html.Br(),
                            html.Span(f"Количество: {order.get('quantity', 'N/A')}", style={'color': '#999', 'fontSize': '0.7em'}),
                            html.Br(),
                            html.Span(f"Стратегия: {order.get('strategy', 'N/A')}", style={'color': '#999', 'fontSize': '0.7em'}),
                            html.Br(),
                            html.Span(f"Причина: {order.get('reason', 'N/A')}", style={'color': '#999', 'fontSize': '0.7em'}),
                        ])
                    ], style={'padding': '8px', 'marginBottom': '8px', 'border': f'1px solid {color}', 'borderRadius': '5px', 'backgroundColor': f'{color}10'})
                )
        else:
            blocks = [html.P("Ожидание ордеров...", style={'color': '#666'})]
        return blocks
