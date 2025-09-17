from __future__ import annotations


async def get_candles(client, figi, from_date, to_date, interval):
    await client._limiter_get.acquire()  # noqa: SLF001
    return await client._services.market_data.get_candles(  # noqa: SLF001
        figi=figi,
        from_=from_date,
        to=to_date,
        interval=interval,
    )


def create_market_data_stream(client):
    return client._services.create_market_data_stream()  # noqa: SLF001



