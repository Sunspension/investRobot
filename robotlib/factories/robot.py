import logging

from robotlib.strategies.base import TradeStrategyBase
from robotlib.robot import AsyncTradingRobot
from robotlib.stats import TradeStatisticsAnalyzer
from robotlib.utils.client import AsyncInvestClient
from robotlib.factories.logger import LoggerFactory

class AsyncTradingRobotFactory:
    @staticmethod
    async def create_robot(
            trade_strategy: TradeStrategyBase,
            client: AsyncInvestClient,
            logging_level: int = logging.INFO,
            figi: str = None,
            ticker: str = None,
            class_code: str = None
    ) -> AsyncTradingRobot:
        response = await client.instrument(figi=figi, ticker=ticker, class_code=class_code)
        instrument = response.instrument
        money, positions = await client.current_postitions(instrument)
        trade_strategy.set_instrument(instrument)
        logger = LoggerFactory.create_logger(trade_strategy.strategy_id, level=logging_level)

        stats = TradeStatisticsAnalyzer(
            positions=positions,
            money=money.to_float(),  # todo: change to Money
            instrument=instrument,
            logger=logger.getChild('stats')
        )
        return AsyncTradingRobot(
            async_client=client,
            trade_strategy=trade_strategy,
            trade_statistics=stats,
            instrument=instrument,
            logger=logger
        )
