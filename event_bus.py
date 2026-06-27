# aria_project/event_bus.py
"""
Thread‑safe publish/subscribe bus.
Modules import `bus` and call:
    bus.publish(EventName, payload)
UI (or any other subscriber) does:
    bus.subscribe(EventName, callback)
"""

from __future__ import annotations
import threading
from typing import Callable, Dict, List, Any


class _EventBus:
    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers: Dict[str, List[Callable[[Any], None]]] = {}

    def subscribe(self, event_name: str, callback: Callable[[Any], None]) -> None:
        with self._lock:
            self._subscribers.setdefault(event_name, []).append(callback)

    def unsubscribe(self, event_name: str, callback: Callable[[Any], None]) -> None:
        with self._lock:
            lst = self._subscribers.get(event_name)
            if lst:
                try:
                    lst.remove(callback)
                except ValueError:
                    pass

    def publish(self, event_name: str, payload: Any = None) -> None:
        # Copy the list to avoid issues if a subscriber unsubscribes during iteration
        with self._lock:
            callbacks = self._subscribers.get(event_name, []).copy()
        for cb in callbacks:
            try:
                cb(payload)
            except Exception as e:          # never let a UI bug crash the core
                print(f"[EventBus] Error in callback for {event_name}: {e}")


# singleton instance used everywhere
bus = _EventBus()