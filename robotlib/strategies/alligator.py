import pandas as pd
from datetime import datetime
from dataclasses import dataclass
from enum import IntEnum
from pandas.core.frame import DataFrame
from collections import deque
from robotlib.strategies.base import TradeStrategyParams, TradeStrategyBase, StrategyDecision
from robotlib.utils.visualizator import Visualizator
from tinkoff.invest import HistoricCandle, SubscriptionInterval
from tinkoff.invest.schemas import Candle


# # Отправка ордера (с минимальной защитой от повторных ордеров)
# if signal in ["BUY", "SELL"] and signal != app.last_signal:
#     direction = OrderDirection.ORDER_DIRECTION_BUY if signal == "BUY" else OrderDirection.ORDER_DIRECTION_SELL
#     try:
#         await orders_service.post_order(
#             figi=FIGI,
#             quantity=1,
#             direction=direction,
#             account_id=ACCOUNT_ID,
#             order_type=OrderType.ORDER_TYPE_MARKET
#         )
#         print(f"Ордер отправлен: {signal}")
#         app.last_signal = signal
#     except Exception as e:
#         print(f"Ошибка отправки ордера: {e}")

# # Обновляем график в UI
# app.update_chart(df, jaw, teeth, lips, signal)

class TradeOrder(IntEnum):
    UNSPECIFIED = 0
    HOLD = 1
    BUY = 2
    SELL = 3

    def __str__(self):
        return self.name
    
@dataclass
class TradeSignal:
    time: datetime = None
    order: TradeOrder = TradeOrder.UNSPECIFIED


class Alligator(TradeStrategyBase):
    PERIOD_JAW, SHIFT_JAW = 2, 1
    PERIOD_TEETH, SHIFT_TEETH = 3, 2
    PERIOD_LIPS, SHIFT_LIPS = 4, 3

    MAX_CANDLES = 100
    MAX_TRADES = 100

    candle_subscription_interval: SubscriptionInterval = SubscriptionInterval.SUBSCRIPTION_INTERVAL_ONE_MINUTE
    order_book_subscription_depth = None
    trades_subscription = None
    last_signal = None

    @property
    def strategy_id(self):
        return "alligator"

    def __init__(self, visualizator: Visualizator = None):
        self.__visualizator = visualizator
        self.__candles_deque = deque(maxlen=self.MAX_CANDLES)
        self.__trades = {}

    def __shifted_sma(self, series: list, period, shift):
        if len(series) < period + shift:
            return pd.Series([None] * len(series))
        sma = pd.Series(series).rolling(window=period).mean()
        return sma.shift(shift)

    def __add_alligator_data(self, df: DataFrame) -> DataFrame:
        closes = df['Close'].tolist()
        jaw = self.__shifted_sma(closes, self.PERIOD_JAW, self.SHIFT_JAW)
        teeth = self.__shifted_sma(closes, self.PERIOD_TEETH, self.SHIFT_TEETH)
        lips = self.__shifted_sma(closes, self.PERIOD_LIPS, self.SHIFT_LIPS)

        df['Jaw'] = pd.Series(jaw, df.index)
        df['Teeth'] = pd.Series(teeth, df.index)
        df['Lips'] = pd.Series(lips, df.index)
        return df

    def __is_uptrend(self, jaw, teeth, lips):
        if lips.empty or teeth.empty or jaw.empty:
            return False
        if pd.isna(lips.iloc[-1]) or pd.isna(teeth.iloc[-1]) or pd.isna(jaw.iloc[-1]):
            return False
        return jaw.iloc[-1] > teeth.iloc[-1] > lips.iloc[-1]

    def __is_downtrend(self, jaw, teeth, lips):
        if lips.empty or teeth.empty or jaw.empty:
            return False
        if pd.isna(lips.iloc[-1]) or pd.isna(teeth.iloc[-1]) or pd.isna(jaw.iloc[-1]):
            return False
        return jaw.iloc[-1] < teeth.iloc[-1] < lips.iloc[-1]

    def __add_to_queue(self, candle: Candle | HistoricCandle):
        dt = candle.time.replace(second=0, microsecond=0)
        open_p = candle.open.units + candle.open.nano / 1e9
        high_p = candle.high.units + candle.high.nano / 1e9
        low_p = candle.low.units + candle.low.nano / 1e9
        close_p = candle.close.units + candle.close.nano / 1e9
        volume = candle.volume

        self.__candles_deque.append(
            {
                'Date': dt,
                'Open': open_p,
                'High': high_p,
                'Low': low_p,
                'Close': close_p,
                'Volume': volume
            }
        )
    
    def __get_singal(self, jaw, teeth, lips) -> TradeSignal:
        signal = TradeSignal()
        if self.__is_uptrend(jaw, teeth, lips):
            signal.order = TradeOrder.BUY
        elif self.__is_downtrend(jaw, teeth, lips):
            signal.order = TradeOrder.SELL
        
        return signal
    
    def __remove_old_trade_items(self):
        counter = len(self.__candles_deque)
        if counter < self.MAX_CANDLES:
            return
        deleted_item = self.__candles_deque.popleft()
        self.__trades.pop(deleted_item['Date'], None)
    
    def __calculate_trade_signal(
            self, 
            candle: Candle | HistoricCandle,
            df: DataFrame
    ) -> TradeSignal:
        # Не совершаем операций если наступила консолидация
        # if df['Consolidation'].iloc[-1] == True:
        #     return TradeSignal()

        jaw, teeth, lips = (df[col] for col in ['Jaw', 'Teeth', 'Lips'])
        signal = self.__get_singal(jaw, teeth, lips)

        if signal.order == TradeOrder.SELL:
            local_max = self.__ao_find_local_max(df)
            if local_max < df['AO'].iloc[-1]:
                signal.order = TradeOrder.BUY
            # Не совершаем продаж, если цена открытия текущей свечи выше предыдущей
            # if df['AO'].iloc[-1] > 0 and df['AO'].iloc[-2] > 0:
            # if df['Close'].iloc[-1] >= df['Close'].iloc[-2]:
                # return TradeSignal()
            # Не совершаем покупок, если цена закрытия текущей свечи ниже предыдущей
        if signal.order == TradeOrder.BUY:
            local_min = self.__ao_find_local_min(df)
            if local_min > df['AO'].iloc[-1]:
                signal.order = TradeOrder.SELL
            # if df['AO'].iloc[-1] < 0 and df['AO'].iloc[-2] < 0:
                # return TradeSignal()

        signal.time = candle.time
        return signal
    
    def __ao_find_local_min(self, df, window=5):
        ao = df['AO']
        local_min = ao == ao.rolling(window, center=True, min_periods=1).min()
        ao_local_mins = ao[local_min]
        
        # if ao_local_mins.empty:
        #     return None
        
        return ao_local_mins.min()
    
    def __ao_find_local_max(self, df, window=5):
        ao = df['AO']
        local_max = ao == ao.rolling(window, center=True, min_periods=1).max()
        ao_local_maxs = ao[local_max]
        
        # if ao_local_maxs.empty:
        #     return None
        
        return ao_local_maxs.max()


    def __draw_data_if_needed(self, canlde_df: DataFrame, trades: dict):
        if self.__visualizator is None:
            return
        self.__visualizator.update_chart(canlde_df, trades)

    def __add_consolidation_data(self, df: DataFrame, threshold=0.0003) -> DataFrame:
        """
        Определяет моменты консолидации:
        когда максимальное расстояние между линиями Аллигатора меньше порога threshold.
        threshold — относительный порог (например, 0.001 = 0.1%)
        """
        consolidation = []
        for i, row in df.iterrows():
            if row[['Jaw', 'Teeth', 'Lips']].isnull().any():
                consolidation.append(False)
                continue
            max_line = max(row['Jaw'], row['Teeth'], row['Lips'])
            min_line = min(row['Jaw'], row['Teeth'], row['Lips'])
            avg_line = (row['Jaw'] + row['Teeth'] + row['Lips']) / 3
            rel_diff = (max_line - min_line) / avg_line
            consolidation.append(rel_diff < threshold)
        df['Consolidation'] = consolidation
        return df
    
    def __add_awesome_oscillator(self, df: DataFrame) -> DataFrame:
        median_price = (df['High'] + df['Low']) / 2
        sma5 = median_price.rolling(window=5).mean()
        sma34 = median_price.rolling(window=34).mean()
        ao = sma5 - sma34
        df['AO'] = ao
        return df

    def load_candles(self, candles):
        for candle in candles:
            self.__add_to_queue(candle=candle)

    def decide(self, market_data, params):
        self.decide_by_candle(market_data.candle, params)

    def decide_by_candle(self, candle: Candle | HistoricCandle, params: TradeStrategyParams):
        self.__add_to_queue(candle=candle)
        candle_df = pd.DataFrame(self.__candles_deque) #self.__prepare_df()
        candle_df = self.__add_alligator_data(candle_df)
        candle_df = self.__add_awesome_oscillator(candle_df)
        candle_df = self.__add_consolidation_data(candle_df)
        signal = self.__calculate_trade_signal(candle, candle_df)
        if signal.time is not None:
            self.__trades[signal.time] = signal.order.name 
        self.__draw_data_if_needed(candle_df, self.__trades)
        self.__remove_old_trade_items()
        return  StrategyDecision()
        