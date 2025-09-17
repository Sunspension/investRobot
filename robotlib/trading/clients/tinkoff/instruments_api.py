from __future__ import annotations

from robotlib.utils.money import Money


async def get_instrument_by_figi(client, figi: str):
    return await client._services.instruments.get_instrument_by(figi=figi)  # noqa: SLF001


async def get_futures_margin(client, figi: str):
    response = await client._services.instruments.get_futures_margin(figi=figi)  # noqa: SLF001
    return {
        'initial_margin_on_buy': Money(response.initial_margin_on_buy).to_float(),
        'initial_margin_on_sell': Money(response.initial_margin_on_sell).to_float(),
        'min_price_increment': Money(response.min_price_increment).to_float(),
        'min_price_increment_amount': Money(response.min_price_increment_amount).to_float(),
    }



