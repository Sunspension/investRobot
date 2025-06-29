import plotly.graph_objs as go

from plotly.graph_objects import Figure
from pandas.core.frame import DataFrame
from dash import Dash, dcc, html, Input, Output

app = Dash(__name__)
app.layout = html.Div([
    dcc.Graph(id='live-graph'),
    dcc.Interval(
        id='interval-component',
        interval=1*1000,
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

    def update_chart(self, candle_df: DataFrame, signals: dict):
        date, open, high, low, close = [
            candle_df[col] for col in ['Date','Open', 'High', 'Low', 'Close']
        ]

        candlestick = go.Candlestick(
            x=date,
            open=open,
            high=high,
            low=low,
            close=close,
            name='Свечи'
        )

        jaw, teeth, lips = [candle_df[col] for col in ['Jaw', 'Teeth', 'Lips']]
        
        line_jaw = go.Scatter(
            x=date, 
            y=jaw, 
            mode='lines', 
            line=dict(color='blue', width=2, dash='dot'), 
            name='Jaw'
        )

        line_teeth = go.Scatter(
            x=date, 
            y=teeth, 
            mode='lines', 
            line=dict(color='red', width=2, dash='dot'), 
            name='Teeth'
        )

        line_lips = go.Scatter(
            x=date, 
            y=lips, 
            mode='lines', 
            line=dict(color='green', width=2, dash='dot'), 
            name='Lips'
        )

        fig = go.Figure(
            data=[
                candlestick, 
                line_jaw, 
                line_teeth, 
                line_lips
            ]
        )

        # Добавляем awesome ascillator
        ao = candle_df['AO']

        fig.add_trace(
            go.Bar(
                x=date,
                y=ao,
                name='Awesome Oscillator',
                marker_color='purple',
                yaxis='y2'
            )
        )

        # fig.add_trace(
        #     go.Bar(
        #         x=date,
        #         y=candle_df['Volume'],
        #         name='Объём',
        #         yaxis='y3',
        #         marker_color='rgba(100, 100, 200, 0.5)'
        #     )
        # )

        for key, value in signals.items():
            if value in ('BUY', 'SELL'):
                x_val = key
                line_color = 'green' if value == 'BUY' else 'red'
                fig.add_vline(
                    x=x_val,
                    line=dict(color=line_color, width=1)
                    # annotation_text=,
                    # annotation_position="top right"
                )

        # # Добавляем заливку фона для периодов консолидации
        # consolidation_periods = []
        # start = None

        # for i in range(len(candle_df)):
        #     if candle_df['Consolidation'].iloc[i]:
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
            template='plotly_dark',
            height=700,
            xaxis_rangeslider_visible=False,
            yaxis=dict(
                title='Цена',
                domain=[0.4, 1]  # верхняя часть графика — свечи
            ),
            yaxis2=dict(
                title='AO',
                domain=[0, 0.25],  # самая нижняя часть — AO
                anchor='x',
                side='left'
            ),
            # yaxis3=dict(
            #     title='Объём',
            #     domain=[0, 0.25],  # нижняя часть — объём
            #     anchor='x'
            # ),
            margin=dict(l=40, r=40, t=40, b=40),
            title="Динамический график Аллигатора"
        )
        
        global current_figure
        current_figure = fig