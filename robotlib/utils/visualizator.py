import plotly.graph_objs as go
import numpy as np

from plotly.graph_objects import Figure
from pandas.core.frame import DataFrame
from dash import Dash, dcc, html, Input, Output
from talipp.indicators import MACD

app = Dash(__name__)
app.layout = html.Div([
    dcc.Graph(id='live-graph'),
    dcc.Interval(
        id='interval-component',
        interval=0.5*1000,
        n_intervals=0
    )
])

current_figure: Figure | None = None

@app.callback(
    Output('live-graph', 'figure'),
    Input('interval-component', 'n_intervals')
)
def update_graph(n):
    return current_figure

class Visualizator:
    def get_dash_app(self):
        return app

    def update_chart(self, df: DataFrame, trades: DataFrame):
        date = df['date']
        open = df['open']
        high = df['high']
        low = df['low']
        close = df['close']

        macd = df['macd']
        signal = df['signal']
        histogram = df['histogram']

        fig = go.Figure()

        fig.add_trace(go.Candlestick(
            x=date,
            open=open,
            high=high,
            low=low,
            close=close,
            name='Свечи'
        ))
        
        fig.add_trace(go.Scatter(
            x=date, 
            y=macd, 
            mode='lines', 
            line=dict(color='blue', width=2), 
            name='macd',
            yaxis='y2'
        ))

        fig.add_trace(go.Scatter(
            x=date,
            y=signal, 
            mode='lines', 
            line=dict(color='red', width=2), 
            name='signal',
            yaxis='y2'
        ))

        fig.add_trace(go.Scatter(
            x=date, 
            y=histogram,
            mode='lines', 
            line=dict(color='green', width=2), 
            name='histogram',
            yaxis='y2'
        ))

        # 3. Гистограмма MACD (нижняя часть, та же ось y2)
        fig.add_trace(go.Bar(
            x=date,
            y=histogram,
            name='Histogram',
            marker_color='green',
            yaxis='y2'
        ))

        df_buy = trades[
            trades['type'].isin(['buy', 'short_buy', 'stop_loss_short_cover'])
            ].sort_values(by='date')
        fig.add_trace(go.Scatter(
            x=df_buy['date'].to_list(),
            y=df_buy['marker_price'].to_list(),
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
            name='Покупка'
        ))

        df_sell = trades[
            trades['type'].isin(['sell', 'short_sell', 'stop_loss_sell'])
            ].sort_values(by='date')
        
        fig.add_trace(go.Scatter(
            x=df_sell['date'].to_list(),
            y=df_sell['marker_price'].to_list(),
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
            name='Продажа'
        ))

        # Добавляем заливку фона для периодов консолидации
        consolidation_periods = []
        start = None

        # for i in range(len(df)):
        #     if df['Consolidation'].iloc[i]:
        #         if start is None:
        #             start = date[i]
        #         end = date[i]
        #     else:
        #         if start is not None:
        #             consolidation_periods.append((start, end))
        #             start = None
        # # Добавляем последний интервал, если он не завершился
        # if start is not None:
        #     consolidation_periods.append((start, end))

        # # Рисуем по одному прямоугольнику на каждый интервал
        # for x0, x1 in consolidation_periods:
        #     fig.add_vrect(
        #         x0=x0,
        #         x1=x1,
        #         fillcolor="LightSalmon",
        #         opacity=0.3,
        #         layer="below",
        #         line_width=0,
        #     )

         
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

        fig.show()
        
        global current_figure
        current_figure = fig
