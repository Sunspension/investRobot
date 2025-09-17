from __future__ import annotations

import asyncio
import time


class TokenBucket:
    """Простой токен-бакет для ограничения RPS.

    capacity: максимальное количество токенов
    fill_rate_per_sec: скорость пополнения (токенов в секунду)
    """

    def __init__(self, capacity: int, fill_rate_per_sec: float) -> None:
        self._capacity = max(1, capacity)
        self._fill_rate = max(0.0, fill_rate_per_sec)
        self._tokens = float(self._capacity)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed <= 0:
            return
        add = elapsed * self._fill_rate
        if add > 0:
            self._tokens = min(self._capacity, self._tokens + add)
            self._last_refill = now

    async def acquire(self, tokens: float = 1.0) -> None:
        async with self._lock:
            while True:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                # Сколько ждать до следующего пополнения хотя бы одного токена
                need = tokens - self._tokens
                wait_sec = max(0.001, need / self._fill_rate if self._fill_rate > 0 else 0.1)
                await asyncio.sleep(wait_sec)


