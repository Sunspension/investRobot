from __future__ import annotations

import random


def compute_backoff_delay(
    retries: int,
    *,
    base_seconds: float = 0.5,
    max_seconds: float = 30.0,
    jitter: str = "full",  # "none" | "half" | "full"
) -> float:
    """Возвращает задержку для экспоненциального backoff с джиттером.

    retries: номер попытки (>=0)
    base_seconds: базовая задержка
    max_seconds: максимум
    jitter: тип джиттера
    """
    if retries < 0:
        retries = 0
    delay = base_seconds * (2 ** retries)
    if delay > max_seconds:
        delay = max_seconds
    if jitter == "none":
        return delay
    if jitter == "half":
        return delay * 0.5 + random.random() * (delay * 0.5)
    # full jitter
    return random.random() * delay


