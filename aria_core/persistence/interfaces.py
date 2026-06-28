# aria_core/persistence/interfaces.py
"""
Backend-agnostic on-disk storage contract used by memory and goals.

Implementations may use any underlying technology (SQLite, JSON files,
shelve, …).  All methods are synchronous; concurrency is the backend's
responsibility.  ARIA Core depends only on this protocol.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, Literal, runtime_checkable


@runtime_checkable
class PersistenceProtocol(Protocol):
    """Backend-agnostic on-disk storage used by memory and goals.

    All methods are synchronous; backend implementations may use any
    underlying technology (SQLite, JSON files, etc.). Concurrency is
    the backend's responsibility.
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def initialize(self) -> None:
        """Create tables/files if missing. Idempotent."""

    # ------------------------------------------------------------------
    # Goals
    # ------------------------------------------------------------------
    def save_goal(self, goal: "Goal") -> None:
        """Upsert a goal by id."""

    def load_all_goals(self) -> list["Goal"]:
        """Return every persisted goal in insertion order."""

    def delete_goal(self, goal_id: str) -> None:
        """No-op if the id is absent."""

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------
    def save_memory_items(self, items: list["MemoryItem"]) -> None:
        """Upsert a batch of items (mixed subtypes allowed)."""

    def load_memory_items(
        self,
        *,
        store: Literal["working", "episodic", "semantic"],
        limit: int = 1000,
    ) -> list["MemoryItem"]:
        """Return most-recent items of the given store, subtype preserved."""

    def update_memory_importance(self, item_id: str, new_importance: float) -> None:
        """Clamp to [0, 1] and persist. No-op if id absent."""
