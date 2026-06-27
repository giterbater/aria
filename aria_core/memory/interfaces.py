# aria_core/memory/interfaces.py
"""
Protocol‑based contract for ARIA's memory subsystem.

Any concrete memory system (SQLite, Qdrant, FAISS, Redis, Neo4j, …) must
implement this protocol.  ARIA Core depends only on the protocol, never on
a concrete class, guaranteeing complete independence from the Language
Cortex and from the storage technology.
"""

from __future__ import annotations

import datetime
from typing import Protocol, Iterable, Tuple, List, Optional, Dict, Any, runtime_checkable

# ----------------------------------------------------------------------
# Shared data models (imported from models.py for brevity in the protocol)
# ----------------------------------------------------------------------
from .models import MemoryItem, WorkingMemoryItem, EpisodicItem, SemanticItem


@runtime_checkable
class MemorySystemProtocol(Protocol):
    """Core contract that ARIA Core will call."""

    # -----------------------------------------------------------------
    # Working memory – short‑term buffer (fixed size or time‑based)
    # -----------------------------------------------------------------
    def store_working(self, item: WorkingMemoryItem) -> None: ...

    def get_working(self, limit: int = 10) -> List[WorkingMemoryItem]: ...

    # ------------------------------------------------------------------
    # Episodic memory – timestamped interaction logs
    # ------------------------------------------------------------------
    def store_episodic(self, item: EpisodicItem) -> None: ...

    def get_episodic(
        self,
        start: Optional[datetime.datetime] = None,
        end: Optional[datetime.datetime] = None,
        limit: int = 100,
    ) -> List[EpisodicItem]: ...

    # ------------------------------------------------------------------
    # Semantic memory – distilled knowledge / facts
    # ------------------------------------------------------------------
    def store_semantic(self, item: SemanticItem) -> None: ...

    def get_semantic(
        self,
        *,
        query: Optional[str] = None,
        limit: int = 50,
    ) -> List[SemanticItem]: ...

    # ------------------------------------------------------------------
    # Relevance‑based retrieval (used by ARIA Core for reasoning)
    # ------------------------------------------------------------------
    def retrieve_relevant(
        self,
        cue: str,
        *,
        working_weight: float = 0.4,
        episodic_weight: float = 0.4,
        semantic_weight: float = 0.2,
        limit: int = 10,
    ) -> List[Tuple[MemoryItem, float]]:
        """
        Return a list of (memory_item, relevance_score) tuples ordered by
        descending relevance.  The concrete implementation decides how to
        blend the three stores; the weights are merely hints.
        """
        ...

    # ------------------------------------------------------------------
    # Importance‑driven housekeeping
    # ------------------------------------------------------------------
    def update_importance(self, item_id: str, delta: float) -> None:
        """Adjust the importance of an existing item (e.g., reinforcement)."""
        ...

    def consolidate(
        self,
        *,
        importance_threshold: float = 0.7,
        max_age: datetime.timedelta = datetime.timedelta(days=1),
    ) -> int:
        """
        Promote qualifying Working/Episodic items to Semantic memory.
        Returns the number of items consolidated.
        """
        ...

    def forget_low_importance(
        self,
        *,
        threshold: float = 0.2,
        older_than: datetime.timedelta = datetime.timedelta(days=30),
    ) -> int:
        """
        Permanently discard items whose importance falls below *threshold*
        and are older than *older_than*.  Returns the number of items
        removed.
        """
        ...

    # ------------------------------------------------------------------
    # Utility / introspection
    # ------------------------------------------------------------------
    def size(self) -> Dict[str, int]:
        """Return approximate counts for each store (useful for monitoring)."""
        ...