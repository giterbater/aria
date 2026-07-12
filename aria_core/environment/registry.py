"""Registry for pluggable ARIA environments."""

from __future__ import annotations

import threading
from typing import Callable

from .contract import Environment

EnvironmentFactory = Callable[..., Environment]

_lock = threading.RLock()
_factories: dict[str, EnvironmentFactory] = {}


def register(name: str, factory: EnvironmentFactory, *, replace: bool = False) -> None:
    """Register an environment factory by name."""

    if not name:
        raise ValueError("Environment name must be non-empty")
    if not callable(factory):
        raise TypeError("Environment factory must be callable")

    with _lock:
        if name in _factories and not replace:
            raise ValueError(f"Environment already registered: {name}")
        _factories[name] = factory


def make(name: str, **kwargs) -> Environment:
    """Create an environment by registered name."""

    with _lock:
        factory = _factories.get(name)
    if factory is None:
        known = ", ".join(sorted(_factories)) or "<none>"
        raise KeyError(f"Unknown environment: {name}. Registered environments: {known}")
    return factory(**kwargs)


def registered() -> tuple[str, ...]:
    """Return registered environment names."""

    with _lock:
        return tuple(sorted(_factories))
