#!/usr/bin/env python3
"""
Модуль для построения графиков визуализации
Создает графики свечей, сигналов и ордеров
"""

from typing import List, Dict, Any, Optional
import pandas as pd
import plotly.graph_objs as go
from plotly.graph_objects import Figure
from robotlib.utils.logger import get_logger

class ChartBuilder:
    """Строитель графиков для визуализации"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def create_trading_chart(
        self, 
        candles_data: List[Dict[str, Any]], 
        signals_data: List[Dict[str, Any]], 
        orders_data: List[Dict[str, Any]],
        current_price: float = 0.0
    ) -> Figure:
        """Создает график для торговли"""
        fig = go.Figure()
        
        if not candles_data:
            fig.add_annotation(
                text="Ожидание данных...",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=20, color="gray")
            )
            return fig
        
        df = pd.DataFrame(candles_data)
        
        # Свечи
        fig.add_trace(go.Candlestick(
            x=df['time'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='Свечи',
            increasing_line_color='#26a69a',
            decreasing_line_color='#ef5350',
            increasing_fillcolor='#26a69a',
            decreasing_fillcolor='#ef5350'
        ))
        
        # Добавляем горизонтальную линию текущей цены
        if not df.empty and current_price > 0:
            fig.add_hline(
                y=current_price,
                line_dash="dash",
                line_color="#FF6B35",
                line_width=1,
                annotation_text=f"Текущая цена: {current_price:.2f} ₽",
                annotation_position="top right",
                annotation_font_color="#FF6B35",
                annotation_font_size=12
            )
        
        # Сигналы покупки/продажи
        self._add_signals_to_chart(fig, signals_data)
        
        # Ордера покупки/продажи
        self._add_orders_to_chart(fig, orders_data)
        
        # Настройка макета
        self._configure_chart_layout(fig)
        
        return fig
    
    def _add_signals_to_chart(self, fig: Figure, signals_data: List[Dict[str, Any]]) -> None:
        """Добавляет сигналы на график"""
        for signal in signals_data[-20:]:  # Последние 20 сигналов
            color = '#00ff88' if signal['type'] == 'buy' else '#ff4444'
            symbol = 'triangle-up' if signal['type'] == 'buy' else 'triangle-down'
            
            # Создаем текст с дополнительной информацией
            signal_text = f"{'🟢 BUY' if signal['type'] == 'buy' else '🔴 SELL'}"
            if 'reason' in signal:
                signal_text += f"<br>{signal['reason']}"
            if 'strength' in signal:
                signal_text += f"<br>Сила: {signal['strength']:.3f}"
            
            fig.add_trace(go.Scatter(
                x=[signal['time']],
                y=[signal['price']],
                mode='markers+text',
                marker=dict(
                    size=15, 
                    color=color,
                    symbol=symbol,
                    line=dict(width=2, color='white')
                ),
                text=[signal_text],
                textposition='top center',
                name=signal['type'].title(),
                showlegend=False,
                hovertemplate=f"<b>{'Покупка' if signal['type'] == 'buy' else 'Продажа'}</b><br>" +
                             f"Цена: {signal['price']:.2f} ₽<br>" +
                             f"Время: %{{x}}<br>" +
                             f"Причина: {signal.get('reason', 'N/A')}<br>" +
                             (f"Количество: {signal.get('quantity', 'N/A')}<br>" if 'quantity' in signal else "") +
                             (f"Стратегия: {signal.get('strategy', 'N/A')}<br>" if 'strategy' in signal else "") +
                             (f"MACD: {signal.get('macd', 'N/A'):.3f}<br>" if 'macd' in signal else "") +
                             (f"Сигнал: {signal.get('signal', 'N/A'):.3f}<br>" if 'signal' in signal else "") +
                             (f"Сила: {signal.get('strength', 'N/A'):.3f}<br>" if 'strength' in signal else "") +
                             "<extra></extra>"
            ))
    
    def _add_orders_to_chart(self, fig: Figure, orders_data: List[Dict[str, Any]]) -> None:
        """Добавляет ордера на график"""
        if not orders_data:
            return
        
        # Покупки (зеленые треугольники вверх)
        buy_orders = [order for order in orders_data if order['type'] in ['buy', 'short_buy', 'stop_loss_short_cover']]
        if buy_orders:
            fig.add_trace(go.Scatter(
                x=[order['time'] for order in buy_orders],
                y=[order['price'] for order in buy_orders],
                mode='markers',
                marker=dict(
                    symbol='triangle-up',
                    color='rgb(50, 205, 50)',
                    size=12,
                    line=dict(
                        color='rgb(0, 150, 0)',
                        width=1
                    )
                ),
                name='Ордера покупки',
                hovertemplate="<b>Ордер покупки</b><br>" +
                             "Цена: %{y:.2f} ₽<br>" +
                             "Время: %{x}<br>" +
                             "Количество: %{customdata[0]}<br>" +
                             "Стратегия: %{customdata[1]}<br>" +
                             "<extra></extra>",
                customdata=[[order.get('quantity', 1), order.get('strategy', 'Unknown')] for order in buy_orders]
            ))
        
        # Продажи (красные треугольники вниз)
        sell_orders = [order for order in orders_data if order['type'] in ['sell', 'short_sell', 'stop_loss_sell']]
        if sell_orders:
            fig.add_trace(go.Scatter(
                x=[order['time'] for order in sell_orders],
                y=[order['price'] for order in sell_orders],
                mode='markers',
                marker=dict(
                    symbol='triangle-down',
                    color='rgb(255, 0, 0)',
                    size=12,
                    line=dict(
                        color='rgb(150, 0, 0)',
                        width=1
                    )
                ),
                name='Ордера продажи',
                hovertemplate="<b>Ордер продажи</b><br>" +
                             "Цена: %{y:.2f} ₽<br>" +
                             "Время: %{x}<br>" +
                             "Количество: %{customdata[0]}<br>" +
                             "Стратегия: %{customdata[1]}<br>" +
                             "<extra></extra>",
                customdata=[[order.get('quantity', 1), order.get('strategy', 'Unknown')] for order in sell_orders]
            ))
    
    def _configure_chart_layout(self, fig: Figure) -> None:
        """Настраивает макет графика"""
        fig.update_layout(
            xaxis_title="Время",
            yaxis_title="Цена (₽)",
            height=600,
            showlegend=True,
            template="plotly_white",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            uirevision="real_data"  # Сохраняет зум и позицию при обновлении
        )
        
        fig.update_xaxes(
            type='date',
            tickformat='%H:%M:%S'
        )
    
    def create_macd_chart(
        self, 
        candles_data: List[Dict[str, Any]], 
        macd_data: List[float] = None,
        signal_data: List[float] = None,
        histogram_data: List[float] = None
    ) -> Figure:
        """Создает график MACD"""
        fig = go.Figure()
        
        if not candles_data:
            fig.add_annotation(
                text="Ожидание данных...",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=20, color="gray")
            )
            return fig
        
        df = pd.DataFrame(candles_data)
        
        # Свечи
        fig.add_trace(go.Candlestick(
            x=df['time'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='Свечи'
        ))
        
        # MACD индикаторы
        if 'macd' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['time'],
                y=df['macd'],
                mode='lines',
                line=dict(color='blue', width=2),
                name='MACD',
                yaxis='y2'
            ))
        
        if 'signal' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['time'],
                y=df['signal'],
                mode='lines',
                line=dict(color='red', width=2),
                name='Signal',
                yaxis='y2'
            ))
        
        if 'histogram' in df.columns:
            fig.add_trace(go.Bar(
                x=df['time'],
                y=df['histogram'],
                name='Histogram',
                marker_color='green',
                yaxis='y2'
            ))
        
        # Настройка макета для MACD
        fig.update_layout(
            height=700,
            xaxis=dict(
                domain=[0, 1],
                rangeslider=dict(visible=False),
                anchor='y1'
            ),
            yaxis=dict(
                domain=[0.3, 1],  # верхняя часть графика (свечи)
                title='Цена',
                anchor='x'
            ),
            yaxis2=dict(
                domain=[0, 0.3],  # нижняя часть графика (MACD)
                title='MACD',
                anchor='x'
            ),
            title="MACD",
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
        )
        
        return fig
