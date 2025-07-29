#!/usr/bin/env python3
"""
Параметры для создания визуализатора
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class VisualizerParams:
    """Параметры для создания визуализатора"""
    figi: str = "FUTIMOEXF000"
    update_interval: int = 1
    with_trading_session: bool = True
    strategy_params: Optional[Dict[str, Any]] = None
