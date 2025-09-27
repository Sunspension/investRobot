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
from config_data.config import load_config

class ChartBuilder:
    """Строитель графиков для визуализации"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def create_trading_chart(
        self, 
        candles_data: List[Dict[str, Any]], 
        orders_data: List[Dict[str, Any]],
        current_price: float = 0.0,
        hide_inactive_time: bool = True
    ) -> Figure:
        """Создает график для торговли"""
        # self.logger.debug(f"ChartBuilder: создаем график с {len(candles_data)} свечами, {len(orders_data)} ордерами")
        fig = go.Figure()
        
        if not candles_data:
            # Создаем пустой график с заголовком
            fig.update_layout(
                title="📊 График цен - Ожидание данных...",
                title_x=0.5,
                xaxis_title="Время",
                yaxis_title="Цена (₽)",
                height=500,
                showlegend=True,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(size=12)
            )
            fig.add_annotation(
                text="🔄 Загрузка исторических данных...",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=18, color="#666"),
                bgcolor="rgba(255,255,255,0.8)",
                bordercolor="#ddd",
                borderwidth=1
            )
            return fig
        
        df = pd.DataFrame(candles_data)
        # Гарантируем хронологический порядок: от старых к новым
        try:
            if not df.empty and 'time' in df.columns:
                df = df.sort_values('time').reset_index(drop=True)
        except Exception:
            pass
        # Защита: приводим цены к числам и отбрасываем некорректные строки
        try:
            for col in ('open', 'high', 'low', 'close'):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            if 'volume' in df.columns:
                df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
            df = df.dropna(subset=['open', 'high', 'low', 'close'])
        except Exception:
            pass
        if df.empty:
            fig.update_layout(
                title="📊 График цен - Нет валидных данных",
                title_x=0.5,
                xaxis_title="Время",
                yaxis_title="Цена (₽)",
                height=500,
                showlegend=True,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(size=12)
            )
            return fig
        # self.logger.debug(f"DataFrame создан: {len(df)} строк, колонки: {list(df.columns)}")
        
        # Свечи
        try:
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
            # self.logger.debug("Свечи добавлены в график")
        except Exception as e:
            self.logger.error(f"❌ Ошибка добавления свечей: {e}")
            # Создаем простой линейный график как fallback
            fig.add_trace(go.Scatter(
                x=df['time'],
                y=df['close'],
                mode='lines',
                name='Цена',
                line=dict(color='#26a69a', width=2)
            ))
        
        # Добавляем горизонтальную линию текущей цены c динамическим цветом и читаемой подписью
        if not df.empty:
            # Нормализуем текущую цену и делаем fallback на последнюю close при нулевом/пустом значении
            cp: float = 0.0
            try:
                cp = float(current_price)
            except Exception:
                cp = 0.0
            if cp <= 0.0:
                try:
                    cp = float(df['close'].iloc[-1])
                except Exception:
                    cp = 0.0
            if cp <= 0.0:
                # Нет валидной цены — не рисуем линию
                pass
            else:
                # Безопасное определение цвета линии текущей цены (более насыщенные цвета)
                green = '#2ecc71'
                red = '#e74c3c'
                neutral = '#444444'
                line_col = neutral
                
                # Определяем цвет на основе последней свечи и текущей цены
                if 'close' in df.columns and 'open' in df.columns and not df.empty:
                    try:
                        last_row = df.iloc[-1]
                        last_close = float(last_row['close'])
                        last_open = float(last_row['open'])
                        current_price = float(cp)
                        
                        # Свеча зеленая если close >= open
                        is_green_candle = last_close >= last_open
                        # Цена растет если текущая цена >= последней close
                        is_price_up = current_price >= last_close
                        
                        # Логика: зеленый если свеча зеленая И цена растет, красный если свеча красная И цена падает
                        if is_green_candle and is_price_up:
                            line_col = green
                        elif not is_green_candle and not is_price_up:
                            line_col = red
                        else:
                            line_col = neutral
                            
                        # Отладочная информация
                        self.logger.debug(f"Price color: candle_green={is_green_candle}, price_up={is_price_up}, color={line_col}")
                        
                    except Exception as e:
                        self.logger.debug(f"Error determining price color: {e}")
                        line_col = neutral

                # Одна непрерывная линия (shape) на всю ширину области графика
                try:
                    fig.add_shape(
                        type='line',
                        xref='paper', x0=0.0, x1=1.0,
                        yref='y', y0=cp, y1=cp,
                        line=dict(color=line_col, width=2, dash='dash'),
                        layer='above'
                    )
                except Exception:
                    pass

                # Подпись прямо на шкале Y: только цена, прямоугольник в цвет линии, текст белый
                try:
                    axis_font_size = None
                    try:
                        axis_font_size = getattr(getattr(fig.layout, 'yaxis', None), 'tickfont', None)
                        axis_font_size = getattr(axis_font_size, 'size', None)
                    except Exception:
                        axis_font_size = None
                    if axis_font_size is None:
                        axis_font_size = getattr(getattr(fig.layout, 'font', None), 'size', None) or 11
                except Exception:
                    axis_font_size = 11

                fig.add_annotation(
                    xref="paper",
                    x=0.0,  # ровно по линии оси Y
                    yref="y",
                    y=cp,
                    text=f"<b>{cp:.1f}</b>",
                    showarrow=False,
                    xanchor="right",  # прилипает к оси слева
                    yanchor="middle",
                    xshift=4,  # смещение вправо на 4px
                    font=dict(color="#ffffff", size=axis_font_size),
                    bgcolor=line_col,
                    bordercolor=line_col,
                    borderwidth=2,
                    borderpad=4,
                    opacity=1.0,
                )

        # Ордера покупки/продажи
        self._add_orders_to_chart(fig, orders_data, candles_data)
        
        # Настройка макета
        self._configure_chart_layout(fig)

        # Скрытие неактивного времени (rangebreaks)
        if hide_inactive_time:
            cfg = load_config()
            def _hm_to_float(hhmm: str) -> float:
                h, m = hhmm.split(":")
                return int(h) + int(m) / 60.0
            # Суббота-воскресенье
            breaks = [dict(bounds=["sat", "mon"])]
            # Ночные часы: два интервала (23:50–24:00 и 00:00–10:00)
            breaks.append(dict(pattern="hour", bounds=[23 + 50/60, 24]))
            breaks.append(dict(pattern="hour", bounds=[0, 10]))
            # Клинринги из конфига
            day_start = _hm_to_float(cfg.clearing_day_start)
            day_end = _hm_to_float(cfg.clearing_day_end)
            eve_start = _hm_to_float(cfg.clearing_evening_start)
            eve_end = _hm_to_float(cfg.clearing_evening_end)
            breaks.append(dict(pattern="hour", bounds=[day_start, day_end]))
            breaks.append(dict(pattern="hour", bounds=[eve_start, eve_end]))
            fig.update_xaxes(rangebreaks=breaks)
        else:
            # Явно очищаем ранее установленные разрывы времени
            fig.update_xaxes(rangebreaks=[])

        # Важно: меняем uirevision при переключении, чтобы Plotly применил обновление layout
        # Делаем uirevision зависящим от последнего времени свечи и состояния тоггла,
        # чтобы при появлении новой свечи ось X переавторассчитывалась.
        try:
            last_key = "0"
            if not df.empty:
                last_key = str(pd.to_datetime(df['time'].iloc[-1]).value)
            fig._layout_obj[u"uirevision"] = f"data_{last_key}_{'hide' if hide_inactive_time else 'show'}"
        except Exception:
            fig._layout_obj[u"uirevision"] = f"data_{len(df)}_{'hide' if hide_inactive_time else 'show'}"

        # self.logger.debug("График создан успешно")
        return fig


    def _add_orders_to_chart(self, fig: Figure, orders_data: List[Dict[str, Any]], candles_data: Optional[List[Dict[str, Any]]] = None) -> None:
        """Добавляет ордера на график"""
        if not orders_data:
            # self.logger.debug("Нет ордеров для добавления на график")
            return
            
        # self.logger.debug(f"Добавляем {len(orders_data)} ордеров на график")
        
        # Небольшой вертикальный отступ для маркеров, чтобы не перекрывать свечи
        def _offset(price: float) -> float:
            try:
                p = float(price)
            except Exception:
                p = 0.0
            # ~0.02% от цены, минимум 0.05
            return max(abs(p) * 0.0002, 0.05)

        # Визуальная нормализация (только для отрисовки):
        # если ордерные цены сильно выбиваются относительно диапазона свечей, пробуем отмасштабировать ×/÷100
        def _vis_price(pr: float) -> float:
            return pr
        try:
            if candles_data:
                _df = pd.DataFrame(candles_data)
                if not _df.empty:
                    lo = float(_df['low'].min())
                    hi = float(_df['high'].max())
                    def _vis_price(pr: float) -> float:  # type: ignore[no-redef]
                        try:
                            v = float(pr)
                        except Exception:
                            return pr
                        # Используем более мягкое масштабирование ×/÷10
                        scale = 10.0
                        hi_band = hi * 2
                        lo_band = lo / 2 if lo != 0 else 0.0
                        if v > hi_band and (v / scale) > lo and (v / scale) < hi_band:
                            return v / scale
                        if v < lo_band and (v * scale) < hi_band and (v * scale) > lo_band:
                            return v * scale
                        return v
        except Exception:
            pass

        # Покупки (зеленые треугольники вверх)
        def _otype(o: Dict[str, Any]) -> str:
            try:
                return str(o.get('direction', '')).lower()
            except Exception:
                return ''

        buy_orders = [
            order for order in (orders_data or [])
            if _otype(order) in ['buy', 'short_buy', 'stop_loss_short_cover']
            and 'time' in order and 'price' in order
        ]
        if buy_orders:
            fig.add_trace(go.Scatter(
                x=[order['time'] for order in buy_orders],
                y=[_vis_price(order['price']) - _offset(order['price']) for order in buy_orders],
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
                             "Причина: %{customdata[2]}<br>" +
                             "Стратегия: %{customdata[1]}<br>" +
                             "<extra></extra>",
                customdata=[[order.get('quantity', 1), order.get('strategy', 'Unknown'), order.get('reason', 'N/A')] for order in buy_orders]
            ))
        
        # Продажи (красные треугольники вниз)
        sell_orders = [
            order for order in (orders_data or [])
            if _otype(order) in ['sell', 'short_sell', 'stop_loss_sell']
            and 'time' in order and 'price' in order
        ]
        if sell_orders:
            fig.add_trace(go.Scatter(
                x=[order['time'] for order in sell_orders],
                y=[_vis_price(order['price']) + _offset(order['price']) for order in sell_orders],
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
                             "Причина: %{customdata[2]}<br>" +
                             "Стратегия: %{customdata[1]}<br>" +
                             "<extra></extra>",
                customdata=[[order.get('quantity', 1), order.get('strategy', 'Unknown'), order.get('reason', 'N/A')] for order in sell_orders]
            ))

    def _configure_chart_layout(self, fig: Figure) -> None:
        """Настраивает макет графика"""
        # self.logger.debug("Настраиваем макет графика")
        fig.update_layout(
            xaxis_title="Время",
            yaxis_title="Цена (₽)",
            height=600,
            showlegend=True,
            template="plotly_white",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            uirevision=None,
            xaxis_rangeslider_visible=False
        )
        
        fig.update_xaxes(
            type='date',
            tickformat='%H:%M:%S',
            autorange=True,
            showgrid=True
        )
        fig.update_yaxes(
            autorange=True,
            tickformat='.1f'  # метки внутри, т.е. с отступом вправо от оси
        )
        
        # self.logger.debug("Макет графика настроен")
    
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
