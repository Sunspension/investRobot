import enum

from datetime import datetime
from typing import Protocol, AsyncGenerator, Optional, List
from robotlib.utils.money import Money
from tinkoff.invest import (
    AsyncClient,
    InstrumentIdType,
    Instrument,
    HistoricCandle,
    CandleInterval,
    CancelOrderResponse,
    GetTradingStatusResponse,
    PostOrderResponse,
    Quotation,
    OrderDirection,
    OrderType,
    InstrumentShort, 
    InstrumentType
)
from tinkoff.invest.market_data_stream.async_market_data_stream_manager import AsyncMarketDataStreamManager



class InvestClient(Protocol):

    async def current_postitions(self, instr: Instrument) -> tuple[Money, int]:
        ...
    async def instrument(
        self, 
        figi: str = None, 
        ticker: str = None, 
        class_code: str = None
    ) -> Instrument:
        ...
    async def get_all_candles(
        self,
        *,
        from_: datetime,
        to: Optional[datetime] = None,
        interval: CandleInterval = CandleInterval(0),
        figi: str = "",
        instrument_id: str = "",
    ) -> AsyncGenerator[HistoricCandle, None]:
        ...
    async def cancel_order(self, *, order_id: str = "") -> CancelOrderResponse:
        ...
    async def trading_status(self, *, figi: str = "", instrument_id: str = "") -> GetTradingStatusResponse:
        ...
    async def create_market_data_stream(self) -> AsyncMarketDataStreamManager:
        ...
    async def post_order(
        self,
        *,
        figi: str = "",
        quantity: int = 0,
        price: Optional[Quotation] = None,
        direction: OrderDirection = OrderDirection(0),
        order_type: OrderType = OrderType(0),
        order_id: str = "",
        instrument_id: str = "",
    ) -> PostOrderResponse:
        ...
    async def order_state(self, order_id: str = None):
        ...
    async def find_instrument_by(
            self,
            *,
            query: str, 
            type: InstrumentType = InstrumentType.INSTRUMENT_TYPE_UNSPECIFIED
    ) -> List[InstrumentShort]:
        ...


class AsyncInvestClient(InvestClient):
    def __init__(
            self,
            app_name,
            account_id,
            token,
            sandbox_token,
            sandbox_mode=False
    ):
        self.__account_id = account_id
        self.__sandbox_mode = sandbox_mode
        self.__app_name = app_name
        self.__token = token
        self.__sandbox_token = sandbox_token

    async def __aenter__(self):
        self.__async_client = AsyncClient(
            token=self.__token, 
            sandbox_token=self.__sandbox_token, 
            app_name=self.__app_name
        )
        self.__services = await self.__async_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.__async_client:
            await self.__async_client.__aexit__(exc_type, exc, tb)
            self.__async_client = None
            self.__services = None
    
    async def instrument(self, figi = None, ticker = None, class_code = None):
        if figi is None:
            if ticker is None or class_code is None:
                    raise ValueError('figi or both ticker and class_code must be not None')
            return await self.__services.instruments.get_instrument_by(
                id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_TICKER,
                class_code=class_code, 
                id=ticker
            )
        return await self.__services.instruments.get_instrument_by(
             id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI, 
             id=figi
        )
    
    async def current_postitions(self, inst: Instrument) -> tuple[Money, int]:
        if self.__sandbox_mode:
            positions = await self.__services.sandbox.get_sandbox_positions(account_id=self.__account_id)
        else:
            positions = await self.__services.operations.get_positions(account_id=self.__account_id)
        instruments = [sec for sec in positions.securities if sec.figi == inst.figi]

        if len(instruments) > 0:
            instrument = instruments[0].balance
        else:
            instrument = 0

        currencies = [m for m in positions.money if m.currency == inst.currency]
        if len(currencies) > 0:
            money = Money(currencies[0].units, currencies[0].nano)
        else:
            money = Money(0, 0)

        return money, instrument
    
    async def get_all_candles(
        self,
        *,
        from_: datetime,
        to: Optional[datetime] = None,
        interval: CandleInterval = CandleInterval(0),
        figi: str = "",
        instrument_id: str = "",
    ) -> AsyncGenerator[HistoricCandle, None]:
        return self.__services.get_all_candles(
            from_=from_, 
            to=to, 
            interval=interval,
            figi=figi,
            instrument_id=instrument_id
        )
        
    async def cancel_order(self, *, order_id = "") -> CancelOrderResponse:
        return self.__services.orders.cancel_order(self, account_id=self.__account_id, order_id=order_id)
    
    async def trading_status(self, *, figi = "", instrument_id = "") -> GetTradingStatusResponse:
        return self.__services.market_data.get_trading_status(figi=figi, instrument_id=instrument_id)
    
    async def create_market_data_stream(self):
        return self.__services.create_market_data_stream()
    
    async def post_order(
            self, 
            *, 
            figi = "", 
            quantity = 0, 
            price = None, 
            direction = OrderDirection(0), 
            order_type = OrderType(0), 
            order_id = "", 
            instrument_id = ""
    ):
        if self.__sandbox_mode:
            return self.__services.sandbox.post_sandbox_order(
                    figi=figi,
                    quantity=quantity,
                    price=price,
                    direction=direction,
                    account_id=self.__account_id,
                    order_type=order_type,
                    order_id=order_id,
                    instrument_id=instrument_id
            )
        return self.__services.orders.post_order(
                figi=figi,
                quantity=quantity,
                price=price,
                direction=direction,
                account_id=self.__account_id,
                order_type=order_type,
                order_id=order_id,
                instrument_id=instrument_id
        )
    
    async def order_state(self, order_id):
        if self.__sandbox_mode:
            return self.__services.sandbox.get_sandbox_order_state(
                account_id=self.__account_id, 
                order_id=order_id
            )
        return self.__services.orders.get_order_state(
            account_id=self.__account_id, 
            order_id=order_id
        )
        
    async def find_instrument_by(
            self, 
            *, 
            query, 
            type = InstrumentType.INSTRUMENT_TYPE_UNSPECIFIED
    ) -> List[InstrumentShort]:
        response = await self.__services.instruments.find_instrument(query=query, instrument_kind=type)
        return response.instruments

    