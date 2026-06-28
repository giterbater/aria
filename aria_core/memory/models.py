# aria_core/memory/models.py
"""
Immutable data containers that travel between ARIA Core and the memory
subsystem.  They contain only plain Python types (no ORM objects) so that
any backend can serialize them however it wishes.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Dict, Optional, List


# ----------------------------------------------------------------------
# Outcome – how an episode ended relative to its intent
# ----------------------------------------------------------------------
class Outcome(str, Enum):
    """Closed-set classification of an episode's outcome.

    Values are strings so they round-trip cleanly through JSON/SQLite.
    """
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    IGNORED = "ignored"
    CORRECTED = "corrected"


# ----------------------------------------------------------------------
# Base class – all memory items share these fields
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class MemoryItem:
    """Common denominator for every memory entry."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    importance: float = field(default=0.5)  # 0.0 … 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def with_importance(self, new_imp: float) -> "MemoryItem":
        """Return a copy with updated importance while preserving concrete type."""
        return replace(
            self,
            importance=max(0.0, min(1.0, new_imp)),
            metadata=dict(self.metadata),
        )


@dataclass(frozen=True)
class WorkingMemoryItem(MemoryItem):
    """Holds the most recent raw inputs / interpretations."""
    structured_input: Any = None  # e.g., StructuredInput from Input Interpreter
    # Optional: any additional context ARIA Core wishes to keep temporarily
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EpisodicItem(MemoryItem):
    """A snapshot of one turn: what ARIA perceived, decided, and the outcome."""
    structured_input: Any = None  # StructuredInput
    decision: Any = None          # ARIDecision
    outcome: Any = None           # e.g., success flag, reward, external feedback
    # Optional free‑form notes (e.g., "user seemed frustrated")
    notes: Optional[str] = None


@dataclass(frozen=True)
class SemanticItem(MemoryItem):
    """A piece of knowledge that ARIA has consolidated over time."""
    # The actual fact could be a string, a tuple, a small graph, etc.
    fact: Any = None
    # Optional source episode(s) that gave rise to this fact
    source_episodic_ids: List[str] = field(default_factory=list)
    # Optional confidence in the fact (derived from consolidation process)
    confidence: float = field(default=0.5)
