import datetime
import asyncio
import threading

from config_data.config import load_config
from robotlib.strategies.base import TradeStrategyParams
from robotlib.strategies.alligator import Alligator
from robotlib.factories.robot import AsyncTradingRobotFactory
from robotlib.robot import AsyncTradingRobot
from robotlib.utils.client import AsyncInvestClient, InstrumentType
from robotlib.utils.visualizator import Visualizator
from tinkoff.invest import InstrumentType

config = load_config()
token = config.tcs_client.token
sandbox_token = config.tcs_client.sandbox_token
account_id = config.tcs_client.id
APP_NAME = "vk_trading_bot"


async def backtest(robot: AsyncTradingRobot):
    stats = await robot.backtest(
        TradeStrategyParams(
            instrument_balance=0, 
            currency_balance=30000,
            pending_orders=[]
        ),
        training_duration=datetime.timedelta(days=1), 
        test_duration=datetime.timedelta(days=3)
    )
    stats.save_to_file('backtest_stats.pickle')

async def trade(robot: AsyncTradingRobot):
    stats = robot.trade()
    stats.save_to_file('stats.pickle')

async def robot(visualizator: Visualizator):
    async with AsyncInvestClient(
        app_name=APP_NAME, 
        account_id=account_id,
        token=token,
        sandbox_token=sandbox_token,
        sandbox_mode=True
    ) as client:
        # result = await client.find_instrument_by(query="IMOEX", type=InstrumentType.INSTRUMENT_TYPE_FUTURES)
        strategy = Alligator(visualizator=visualizator)
        robot = await AsyncTradingRobotFactory.create_robot(
            trade_strategy=strategy, 
            client=client,
            ticker='IMOEXF', 
            class_code= 'SPBFUT'
        )

        await backtest(robot)
        # await trade(robot)

def run_dash_app(app):
    # Запускаем Dash сервер (блокирующий вызов)
    # use_reloader=False чтобы избежать двойного запуска
    app.run(use_reloader=False)

async def main_async_task(visualizator):
    await robot(visualizator)

if __name__ == '__main__':
    visualizator = Visualizator()
    app = visualizator.get_dash_app()

    dash_thread = threading.Thread(target=run_dash_app, args=(app,), daemon=True)
    dash_thread.start()

    asyncio.run(main_async_task(visualizator))

    # Если нужно, можно дождаться завершения потока сервера (обычно сервер работает постоянно)
    # dash_thread.join()