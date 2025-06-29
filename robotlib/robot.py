import datetime
import logging
import uuid
import asyncio

from dataclasses import dataclass
from tinkoff.invest import (
    Candle,
    CandleInstrument,
    CandleInterval,
    InfoInstrument,
    Instrument,
    MarketDataResponse,
    MoneyValue,
    OrderBookInstrument,
    OrderDirection,
    OrderExecutionReportStatus,
    OrderState,
    PostOrderResponse,
    Quotation,
    TradeInstrument
)
from tinkoff.invest.exceptions import InvestError
from tinkoff.invest.services import MarketDataStreamManager
from robotlib.strategies.base import TradeStrategyBase, TradeStrategyParams, RobotTradeOrder
from robotlib.stats import TradeStatisticsAnalyzer
from robotlib.utils.money import Money
from robotlib.utils.client import AsyncInvestClient


@dataclass
class OrderExecutionInfo:
    direction: OrderDirection
    lots: int = 0
    amount: float = 0.0


class AsyncTradingRobot:
    __orders_executed: dict[str, OrderExecutionInfo]  # order_id -> executed lots

    def __init__(
            self,
            async_client: AsyncInvestClient,
            trade_strategy: TradeStrategyBase,
            trade_statistics: TradeStatisticsAnalyzer,
            instrument: Instrument,
            logger: logging.Logger
    ):
        self.__async_client = async_client
        self.__strategy = trade_strategy
        self.__statistics = trade_statistics
        self.__orders_executed = {}
        self.__logger = logger
        self.__instrument = instrument

    async def trade(self) -> TradeStatisticsAnalyzer:
        self.__logger.info('Start trading')

        self.__strategy.load_candles(
            list(
                await self._load_historic_data(
                    datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
                )
            )
        )

        trading_status = await self.__async_client.trading_status(figi=self.__instrument.figi)
        if not trading_status.market_order_available_flag:
            self.__logger.warning('Market trading is not available now.')

        market_data_stream: MarketDataStreamManager = await self.__async_client.create_market_data_stream()
        if self.__strategy.candle_subscription_interval:
            market_data_stream.candles.subscribe([
                    CandleInstrument(
                        figi=self.__instrument.figi,
                        interval=self.__strategy.candle_subscription_interval)
            ])
        if self.__strategy.order_book_subscription_depth:
            market_data_stream.order_book.subscribe([
                OrderBookInstrument(
                    figi=self.__instrument.figi,
                    depth=self.__strategy.order_book_subscription_depth)
            ])
        if self.__strategy.trades_subscription:
            market_data_stream.trades.subscribe([
                TradeInstrument(figi=self.__instrument.figi)
            ])
        market_data_stream.info.subscribe([
            InfoInstrument(figi=self.__instrument.figi)
        ])
        self.__logger.debug(
            f'Subscribed to MarketDataStream, '
            f'interval: {self.__strategy.candle_subscription_interval}'
        )
        try:
            for market_data in market_data_stream:
                self.__logger.debug(f'Received market_data {market_data}')
                if market_data.candle:
                    self._on_update(market_data)
                if market_data.trading_status and market_data.trading_status.market_order_available_flag:
                    self.__logger.info(f'Trading is limited. Current status: {market_data.trading_status}')
                    break
        except InvestError as error:
            self.__logger.info(f'Caught exception {error}, stopping trading')
            market_data_stream.stop()
        return self.__statistics

    async def backtest(
            self,
            initial_params: TradeStrategyParams, 
            test_duration: datetime.timedelta,
            training_duration: datetime.timedelta = None
    ) -> TradeStatisticsAnalyzer:
        trade_statistics = TradeStatisticsAnalyzer(
            positions=initial_params.instrument_balance,
            money=initial_params.currency_balance,
            instrument=self.__instrument,
            logger=self.__logger
        )

        now = datetime.datetime.now(datetime.timezone.utc)
        if training_duration:
            from_time = now - test_duration - training_duration
            to_time = now - test_duration
            training = [item async for item in self._load_historic_data(from_time, to_time)]
            self.__strategy.load_candles(list(training))

        test_data = [item async for item in self._load_historic_data(now - test_duration)]

        params = initial_params
        for candle in test_data:
            # await asyncio.sleep(0.5)
            price = self._convert_from_quotation(candle.close)
            robot_decision = self.__strategy.decide_by_candle(candle, params)

            trade_order = robot_decision.robot_trade_order
            if trade_order:
                assert trade_order.quantity > 0
                if trade_order.direction == OrderDirection.ORDER_DIRECTION_SELL:
                    assert trade_order.quantity >= params.instrument_balance, \
                        f'Cannot execute order {trade_order}. Params are {params}'  # TODO: better logging
                    params.instrument_balance -= trade_order.quantity
                    params.currency_balance += trade_order.quantity * price * self.__instrument.lot
                else:
                    assert trade_order.quantity * self.__instrument.lot * price <= params.currency_balance, \
                        f'Cannot execute order {trade_order}. Params are {params}'  # TODO: better logging
                    params.instrument_balance += trade_order.quantity
                    params.currency_balance -= trade_order.quantity * price * self.__instrument.lot

                trade_statistics.add_backtest_trade(
                    quantity=trade_order.quantity, 
                    price=candle.close, 
                    direction=trade_order.direction
                )

        return trade_statistics

    @staticmethod
    def _convert_from_quotation(amount: Quotation | MoneyValue) -> float | None:
        if amount is None:
            return None
        return amount.units + amount.nano / (10 ** 9)

    def _on_update(
            self, 
            market_data: MarketDataResponse
    ):
        self._check_trade_orders()
        params = TradeStrategyParams(
            instrument_balance=self.__statistics.get_positions(),
            currency_balance=self.__statistics.get_money(),
            pending_orders=self.__statistics.get_pending_orders()
        )

        self.__logger.debug(f'Received market_data {market_data}. Running strategy with params {params}')
        strategy_decision = self.__strategy.decide(market_data, params)
        self.__logger.debug(f'Strategy decision: {strategy_decision}')

        if len(strategy_decision.cancel_orders) > 0:
            self._cancel_orders(orders=strategy_decision.cancel_orders)

        trade_order = strategy_decision.robot_trade_order
        if trade_order and self._validate_strategy_order(order=trade_order, candle=market_data.candle):
            self._post_trade_order(trade_order=trade_order)

    def _validate_strategy_order(
            self, 
            order: RobotTradeOrder, 
            candle: Candle
    ):
        if order.direction == OrderDirection.ORDER_DIRECTION_BUY:
            price = order.price or Money(candle.close)
            total_cost = price * self.__instrument.lot * order.quantity
            balance = self.__statistics.get_money()
            
            if total_cost.to_float() > self.__statistics.get_money():
                self.__logger.warning(
                    f'Strategy decision cannot be executed. '
                    f'Requested buy cost: {total_cost}, balance: {balance}'
                )
                return False
        else:
            instrument_balance = self.__statistics.get_positions()
            if order.quantity > instrument_balance:
                self.__logger.warning(
                    f'Strategy decision cannot be executed. '
                    f'Requested sell quantity: {order.quantity}, balance: {instrument_balance}'
                )
                return False
        return True

    async def _load_historic_data(
            self,
            from_time: datetime.datetime, 
            to_time: datetime.datetime = None
    ):
        try:
            async for candle in await self.__async_client.get_all_candles(
                from_=from_time,
                to=to_time,
                interval=CandleInterval.CANDLE_INTERVAL_1_MIN,
                figi=self.__instrument.figi
            ):
                yield candle
        except InvestError as error:
            self.__logger.error(f'Failed to load historical data. Error: {error}', exc_info=True)

    async def _cancel_orders(self, orders: list[OrderState]):
        async def cancel(order):
            try:
                await self.__async_client.cancel_order(order_id=order.order_id)
                self.__statistics.cancel_order(order_id=order.order_id)
            except InvestError as error:
                self.__logger.error(f'Failed to cancel order {order.order_id}. Error: {error}', exc_info=True)

        await asyncio.gather(*(cancel(order) for order in orders))

    async def _post_trade_order(
            self, 
            trade_order: RobotTradeOrder
    ) -> PostOrderResponse | None:
        try:
            order = await self.__async_client.post_order(
                figi=self.__instrument.figi,
                quantity=trade_order.quantity,
                price=trade_order.price.to_quotation() if trade_order.price is not None else None,
                direction=trade_order.direction,
                order_type=trade_order.order_type,
                order_id=str(uuid.uuid4())
            )

        except InvestError as error:
            self.__logger.error(f'Posting trade order failed :(. Order: {trade_order}; Exception: {error}')
            return
        
        self.__logger.info(f'Placed trade order {order}')
        self.__orders_executed[order.order_id] = OrderExecutionInfo(direction=trade_order.direction)
        self.__statistics.add_trade(order)

        return order

    def _check_trade_orders(self):
        self.__logger.debug(f'Updating trade orders info. Current trade orders num: {len(self.__orders_executed)}')
        orders_executed = list(self.__orders_executed.items())
        
        for order_id in orders_executed:
            order_state = self.__async_client.order_state(order_id=order_id)
            self.__statistics.add_trade(trade=order_state)

            match order_state.execution_report_status:
                case OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_FILL:
                    self.__logger.info(f'Trade order {order_id} has been FULLY FILLED')
                    self.__orders_executed.pop(order_id)
                case OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_REJECTED:
                    self.__logger.warning(f'Trade order {order_id} has been REJECTED')
                    self.__orders_executed.pop(order_id)
                case OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_CANCELLED:
                    self.__logger.warning(f'Trade order {order_id} has been CANCELLED')
                    self.__orders_executed.pop(order_id)
                case OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_PARTIALLYFILL:
                    self.__logger.info(f'Trade order {order_id} has been PARTIALLY FILLED')
                    self.__orders_executed[order_id] = OrderExecutionInfo(
                        lots=order_state.lots_executed,
                        amount=order_state.total_order_amount,
                        direction=order_state.direction
                    )
                case _:
                    self.__logger.debug(f'No updates on order {order_id}')

        self.__logger.debug(f'Successfully updated trade orders. New trade orders num: {len(self.__orders_executed)}')
