from __future__ import annotations

from typing import Iterable, List


def _local_peaks_indices(values: List[float]) -> List[int]:
    n = len(values)
    if n < 3:
        return []
    peaks = []
    for i in range(1, n - 1):
        if values[i] > values[i - 1] and values[i] > values[i + 1]:
            peaks.append(i)
    return peaks


def _local_troughs_indices(values: List[float]) -> List[int]:
    n = len(values)
    if n < 3:
        return []
    troughs = []
    for i in range(1, n - 1):
        if values[i] < values[i - 1] and values[i] < values[i + 1]:
            troughs.append(i)
    return troughs


def _prominence(values: List[float], idx: int) -> float:
    # Simple, robust prominence estimate suitable for small windows.
    v = values[idx]
    left_min = min(values[: idx + 1]) if idx > 0 else v
    right_min = min(values[idx:]) if idx < len(values) - 1 else v
    return v - max(left_min, right_min)


def _prominence_trough(values: List[float], idx: int) -> float:
    # For troughs, invert definition (depth below surrounding maxima)
    v = values[idx]
    left_max = max(values[: idx + 1]) if idx > 0 else v
    right_max = max(values[idx:]) if idx < len(values) - 1 else v
    return max(left_max, right_max) - v


def find_peaks_indices(data: Iterable[float], prominence: float = 0.0) -> List[int]:
    values = list(float(x) for x in data)
    peaks = _local_peaks_indices(values)
    if prominence <= 0:
        return peaks
    return [i for i in peaks if _prominence(values, i) >= prominence]


def find_troughs_indices(data: Iterable[float], prominence: float = 0.0) -> List[int]:
    values = list(float(x) for x in data)
    troughs = _local_troughs_indices(values)
    if prominence <= 0:
        return troughs
    return [i for i in troughs if _prominence_trough(values, i) >= prominence]


