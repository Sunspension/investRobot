import asyncio
import threading
import pytz
import sys
import os
import pandas as pd

from datetime import datetime
from robotlib.utils.logger import get_logger

# Добавляем корневую папку проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_data.config import load_config

from robotlib.utils.visualizator import Visualizator
from tinkoff.invest.exceptions import InvestError
from tinkoff.invest import CandleInterval, InstrumentType
from robotlib.strategies.strategy_manager import StrategyManager
from robotlib.strategies.long import LongStrategy
from robotlib.strategies.short import ShortStrategy
from robotlib.signal_manager import SignalManager
from robotlib.trading.risk_manager import RiskManager, RiskLimits
from robotlib.trading.portfolio_manager import PortfolioManager
from robotlib.trading.tinkoff_api_client import TinkoffAPIClient
from robotlib.utils.money import Money
from tests.mocks import MockAPIClient, MockPortfolioManager




config = load_config()
token = config.tcs_client.token
sandbox_token = config.tcs_client.sandbox_token
account_id = config.tcs_client.id
APP_NAME = "vk_trading_bot"

async def backtest(
        visualizator: Visualizator, 
        from_time: str = "2025-07-16 7:00",
        to_time: str = "2025-07-16 19:00",
        use_mocks: bool = True
    ):
        if use_mocks:
            print("🧪 Режим тестирования: Используем моки для быстрого тестирования")
            # Используем моки для тестирования
            async with MockAPIClient(deposit=400000) as api_client:
                from_time = _to_msk_date(from_time)
                to_time = _to_msk_date(to_time)
                figi = "FUTIMOEXF000"
                
                # Загружаем реальные исторические данные через TinkoffAPIClient
                async with TinkoffAPIClient(token, account_id, sandbox_token) as real_api_client:
                    training = [item async for item in _load_historic_data(real_api_client, figi, from_time, to_time)]
                
                deposit=400000
                percent_from_deposit=50
                items_per_trade=20

                # Создаем мок менеджеры для тестирования
                portfolio_manager = MockPortfolioManager(api_client)
        else:
            print("🚀 Режим продакшн: Используем реальные компоненты")
            # Используем реальные компоненты
            async with TinkoffAPIClient(token, account_id, sandbox_token) as api_client:
                from_time = _to_msk_date(from_time)
                to_time = _to_msk_date(to_time)
                figi = "FUTIMOEXF000"
                training = [item async for item in _load_historic_data(api_client, figi, from_time, to_time)]
                
                deposit=400000
                percent_from_deposit=50
                items_per_trade=20

                # Создаем реальные менеджеры
                portfolio_manager = PortfolioManager(api_client)
        
        # Создаем общие компоненты
        risk_limits = RiskLimits(
            max_daily_loss=deposit * 0.1,
            max_position_size=deposit * 0.5,
            percent_from_deposit=percent_from_deposit,
            items_per_trade=items_per_trade,
            stop_loss_threshold=5.0
        )
        risk_manager = RiskManager(portfolio_manager, risk_limits)
        
        long_strategy = LongStrategy(risk_manager, portfolio_manager)
        short_strategy = ShortStrategy(risk_manager, portfolio_manager)
        
        # Используем лучшие параметры из оптимизации (60,700₽ доход!)
        signal_manager = SignalManager(
            macd_fast=6,           # Лучший параметр
            macd_slow=16,          # Лучший параметр
            macd_signal=7,         # Лучший параметр
            atr_period=10,         # Лучший параметр
            lookback_min=4,        # Лучший параметр
            lookback_max=19,       # Лучший параметр
            peak_prominence=0.15   # Лучший параметр
        )
        
        strategy_manager = StrategyManager(
            signal_manager=signal_manager, 
            risk_manager=risk_manager,
            portfolio_manager=portfolio_manager,
            strategies=[long_strategy, short_strategy]
        )

        for candle in training:
            await strategy_manager.on_candle(candle)
        strategy_manager.close_position(training[-1])
        strategy_manager.print_trades()
        income = strategy_manager.income
        print(f"Income after trade is: {income} with number of trades: {len(strategy_manager.trades)}")
        
        # Получаем готовые DataFrame из StrategyManager
        trades_df = strategy_manager.trades
        candles_df = strategy_manager.candles
        print(f"📊 Получено {len(trades_df)} сделок и {len(candles_df)} свечей из StrategyManager")
        
        visualizator.update_chart(candles_df, trades_df)

async def _load_historic_data(
    client: TinkoffAPIClient,
    figi: str,
    from_time: datetime, 
    to_time: datetime = None
):
    try:
        response = await client.get_candles(
            figi=figi,
            from_date=from_time,
            to_date=to_time,
            interval=CandleInterval.CANDLE_INTERVAL_1_MIN
        )
        if response and response.candles:
            for candle in response.candles:
                yield candle
    except InvestError as error:
        print(f'Failed to load historical data. Error: {error}', exc_info=True)

def _to_msk_date(date: str, tz_info=False) -> datetime:
    dt_naive = datetime.strptime(date, "%Y-%m-%d %H:%M")
    moscow_tz = pytz.timezone("Europe/Moscow")
    # Локализуем datetime, привязывая его к московскому времени
    dt_moscow = moscow_tz.localize(dt_naive)
    return dt_moscow if tz_info else dt_moscow.replace(tzinfo=None)

def run_dash_app(app):
    # Запускаем Dash сервер (блокирующий вызов)
    # use_reloader=False чтобы избежать двойного запуска
    app.run(use_reloader=False)

async def main_async_task(visualizator, use_mocks: bool = True):
    await backtest(visualizator, use_mocks=use_mocks)

if __name__ == '__main__':
    visualizator = Visualizator()
    app = visualizator.get_dash_app()

    dash_thread = threading.Thread(target=run_dash_app, args=(app,), daemon=True)
    dash_thread.start()

    # Переключатель: True = моки (быстро), False = реальные компоненты (медленно)
    USE_MOCKS = True
    asyncio.run(main_async_task(visualizator, use_mocks=USE_MOCKS))

    # Если нужно, можно дождаться завершения потока сервера (обычно сервер работает постоянно)
    # dash_thread.join()
