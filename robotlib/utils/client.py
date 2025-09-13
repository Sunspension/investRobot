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
    InstrumentType,
    InstrumentResponse
)
from tinkoff.invest.market_data_stream.async_market_data_stream_manager import AsyncMarketDataStreamManager


class InvestClient(Protocol):
    async def current_postitions(self, instr: Instrument) -> tuple[Money, int]:
        ...
    async def instrument_info(
        self, 
        figi: str = None, 
        ticker: str = None, 
        class_code: str = None
    ) -> InstrumentResponse:
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
        self._account_id = account_id
        self._sandbox_mode = sandbox_mode
        self._app_name = app_name
        self._token = token
        self._sandbox_token = sandbox_token

    async def __aenter__(self):
        self._async_client = AsyncClient(
            token=self._token, 
            sandbox_token=self._sandbox_token, 
            app_name=self._app_name
        )
        self._services = await self._async_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._async_client:
            await self._async_client.__aexit__(exc_type, exc, tb)
            self._async_client = None
            self._services = None
    
    async def instrument_info(self, figi = None, ticker = None, class_code = None) -> InstrumentResponse:
        if figi is None:
            if ticker is None or class_code is None:
                    raise ValueError('figi or both ticker and class_code must be not None')
            return await self._services.instruments.get_instrument_by(
                id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_TICKER,
                class_code=class_code, 
                id=ticker
            )
        return await self._services.instruments.get_instrument_by(
             id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI, 
             id=figi
        )
    
    async def current_postitions(self, inst: Instrument) -> tuple[Money, int]:
        if self._sandbox_mode:
            positions = await self._services.sandbox.get_sandbox_positions(account_id=self._account_id)
        else:
            positions = await self._services.operations.get_positions(account_id=self._account_id)
        instruments = [sec for sec in positions.securities if sec.figi == inst.figi]

        if len(instruments) > 0:
            balance = instruments[0].balance
        else:
            balance = 0

        currencies = [m for m in positions.money if m.currency == inst.currency]
        if len(currencies) > 0:
            money = Money(currencies[0].units, currencies[0].nano)
        else:
            money = Money(0, 0)

        return money, balance
    
    async def get_all_candles(
        self,
        *,
        from_: datetime,
        to: Optional[datetime] = None,
        interval: CandleInterval = CandleInterval(0),
        figi: str = "",
        instrument_id: str = "",
    ) -> AsyncGenerator[HistoricCandle, None]:
        return self._services.get_all_candles(
            from_=from_, 
            to=to, 
            interval=interval,
            figi=figi,
            instrument_id=instrument_id
        )
        
    async def cancel_order(self, *, order_id = "") -> CancelOrderResponse:
        return self._services.orders.cancel_order(self, account_id=self._account_id, order_id=order_id)
    
    async def trading_status(self, *, figi = "", instrument_id = "") -> GetTradingStatusResponse:
        return self._services.market_data.get_trading_status(figi=figi, instrument_id=instrument_id)
    
    async def create_market_data_stream(self):
        return self._services.create_market_data_stream()
    
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
    ) -> PostOrderResponse:
        if self._sandbox_mode:
            return self._services.sandbox.post_sandbox_order(
                    figi=figi,
                    quantity=quantity,
                    price=price,
                    direction=direction,
                    account_id=self._account_id,
                    order_type=order_type,
                    order_id=order_id,
                    instrument_id=instrument_id
            )
        return self._services.orders.post_order(
                figi=figi,
                quantity=quantity,
                price=price,
                direction=direction,
                account_id=self._account_id,
                order_type=order_type,
                order_id=order_id,
                instrument_id=instrument_id
        )
    
    async def order_state(self, order_id):
        if self._sandbox_mode:
            return self._services.sandbox.get_sandbox_order_state(
                account_id=self._account_id, 
                order_id=order_id
            )
        return self._services.orders.get_order_state(
            account_id=self._account_id, 
            order_id=order_id
        )
        
    async def find_instrument_by(
            self, 
            *, 
            query, 
            type = InstrumentType.INSTRUMENT_TYPE_UNSPECIFIED
    ) -> List[InstrumentShort]:
        response = await self._services.instruments.find_instrument(query=query, instrument_kind=type)
        return response.instruments

    
