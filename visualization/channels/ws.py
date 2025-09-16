from __future__ import annotations

import json
import threading
import time
from typing import Any, Dict, Set

from robotlib.utils.logger import get_logger


class WebSocketHub:
    """Регистр подключений WS и фонового тикера.

    Выделен из DashEventVisualizer для переиспользования.
    """

    def __init__(self) -> None:
        self._logger = get_logger(__name__)
        self._connections: Set[Any] = set()
        self._running: bool = False
        self._ticker_thread: threading.Thread | None = None

    def add(self, ws: Any) -> None:
        self._connections.add(ws)

    def remove(self, ws: Any) -> None:
        if ws in self._connections:
            self._connections.discard(ws)

    def broadcast(self, payload: Dict[str, Any]) -> None:
        if not self._connections:
            return
        message = json.dumps(payload, default=str)
        dead = []
        for ws in list(self._connections):
            try:
                ws.send(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)

    def start_ticker(self) -> None:
        if self._ticker_thread and self._ticker_thread.is_alive():
            return
        self._running = True

        def _ticker_loop():
            while self._running:
                try:
                    self.broadcast({"type": "tick", "t": int(time.time())})
                except Exception:
                    pass
                time.sleep(1)

        self._ticker_thread = threading.Thread(target=_ticker_loop, daemon=True)
        self._ticker_thread.start()

    def stop_ticker(self) -> None:
        self._running = False
        if self._ticker_thread and self._ticker_thread.is_alive():
            self._ticker_thread.join(timeout=2)


