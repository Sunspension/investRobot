from __future__ import annotations


async def get_portfolio(client):
    await client._limiter_get.acquire()  # noqa: SLF001
    if client._sandbox_token:  # noqa: SLF001
        return await client._services.sandbox.get_sandbox_portfolio(account_id=client._account_id)  # noqa: SLF001
    return await client._services.operations.get_portfolio(account_id=client._account_id)  # noqa: SLF001


async def get_positions(client):
    await client._limiter_get.acquire()  # noqa: SLF001
    if client._sandbox_token:  # noqa: SLF001
        return await client._services.sandbox.get_sandbox_positions(account_id=client._account_id)  # noqa: SLF001
    return await client._services.operations.get_positions(account_id=client._account_id)  # noqa: SLF001


async def get_operations_history(client, from_date, to_date):
    await client._limiter_get.acquire()  # noqa: SLF001
    if client._sandbox_token:  # noqa: SLF001
        return await client._services.sandbox.get_sandbox_operations(  # noqa: SLF001
            account_id=client._account_id,  # noqa: SLF001
            from_=from_date,
            to=to_date,
        )
    return await client._services.operations.get_operations(  # noqa: SLF001
        account_id=client._account_id,  # noqa: SLF001
        from_=from_date,
        to=to_date,
    )



