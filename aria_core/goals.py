# aria_core/goals.py
"""
Simple goal representation and manager.
Goals are lightweight objects that ARIA Core can consult when deciding
what to do.  The manager keeps a list of active goals and can return
those that are relevant to a given cue (e.g., the current structured
input).

Milestone 2: an optional :class:`PersistenceProtocol` backend can be
supplied; if present, every ``add_goal`` / ``remove_goal`` call is
mirrored to the backend and the manager is hydrated from it on
construction.
"""

from __future__ import annotations

import datetime
import json
import sqlite3
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional

from aria_core.persistence.interfaces import PersistenceProtocol

if TYPE_CHECKING:  # pragma: no cover – typing only
    from aria_core.memory.models import MemoryItem


@dataclass(frozen=True)
class Goal:
    """A goal that ARIA's internal goal model. """
    id: str = field(default_factory=lambda: str(__import__('uuid').uuid4()))
    description: str = ""          # human‑readable description
    priority: float = 1.0          # higher = more important
    deadline: Optional[datetime.datetime] = None  # optional time bound
    # Any extra metadata the caller wants to store (e.g., required resources)
    metadata: dict = field(default_factory=dict)


class GoalManager:
    """
    Holds the set of active goals and provides relevance lookup.

    Without a ``persistence`` backend, behaviour is identical to the
    pre-M2 manager: an in-memory list, no on-disk state.  With a
    backend, every mutation is forwarded and the manager is hydrated
    from the backend on construction.
    """

    def __init__(
        self,
        goals: Optional[List[Goal]] = None,
        *,
        persistence: Optional[PersistenceProtocol] = None,
    ):
        self._persistence = persistence
        if persistence is not None:
            persistence.initialize()
            # Hydrate from disk so list_goals / relevant_goals reflect
            # the persisted state, not the (typically empty) ``goals`` arg.
            self._goals: List[Goal] = persistence.load_all_goals()
            # Caller-supplied goals are added on top, but only if the
            # backend did not already know about them.
            existing_ids = {g.id for g in self._goals}
            for g in goals or []:
                if g.id not in existing_ids:
                    self._goals.append(g)
                    persistence.save_goal(g)
        else:
            self._goals: List[Goal] = list(goals or [])

    # -----------------------------------------------------------------
    # Goal lifecycle (simple add/remove)
    # -----------------------------------------------------------------
    def add_goal(self, goal: Goal) -> None:
        self._goals.append(goal)
        if self._persistence is not None:
            self._persistence.save_goal(goal)

    def remove_goal(self, goal_id: str) -> None:
        self._goals = [g for g in self._goals if g.id != goal_id]
        if self._persistence is not None:
            self._persistence.delete_goal(goal_id)

    def list_goals(self) -> List[Goal]:
        return list(self._goals)

    # -----------------------------------------------------------------
    # Relevance – very light‑weight keyword match.
    # Replace with a proper embedding‑based search in a production swap.
    # ------------------------------------------------------------------
    def relevant_goals(self, cue: str, *, limit: int = 5) -> List[Goal]:
        """
        Return goals whose description shares any token with *cue*.
        Ordered by priority (descending).
        """
        cue_tokens = set(cue.lower().split())
        scored: List[Goal] = []
        for g in self._goals:
            desc_tokens = set(g.description.lower().split())
            if cue_tokens & desc_tokens:          # any overlap
                scored.append(g)
        scored.sort(key=lambda g: g.priority, reverse=True)
        return scored[:limit]


# ---------------------------------------------------------------------
# SQLite-backed implementation of PersistenceProtocol.
#
# Lives in the goals module (per the M2 contract, which says
# ``aria_core/goals.py`` is the right home for ``SQLiteGoalStore``).
# Other backends can implement the same protocol independently.
# ---------------------------------------------------------------------
class SQLiteGoalStore(PersistenceProtocol):
    """A SQLite-backed ``PersistenceProtocol`` for goals and memory.

    Uses the standard library's :mod:`sqlite3` only.  Two tables:

    * ``goals`` — one row per goal, ``metadata`` stored as JSON.
    * ``memory_items`` — see :mod:`aria_core.memory.sqlite_memory_system`
      for the canonical schema.  This class only touches the ``goals``
      table; ``memory_items`` access is intentionally left to the
      dedicated memory backend to keep responsibilities separate.
    """

    def __init__(self, db_path):
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.initialize()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------
    def initialize(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS goals (
                    id TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    priority REAL NOT NULL,
                    deadline TEXT,
                    metadata TEXT
                );
                """
            )

    # ------------------------------------------------------------------
    # Goals
    # ------------------------------------------------------------------
    def save_goal(self, goal: Goal) -> None:
        deadline_iso = (
            goal.deadline.isoformat() if goal.deadline is not None else None
        )
        metadata_json = json.dumps(goal.metadata or {})
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO goals (id, description, priority, deadline, metadata)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    description=excluded.description,
                    priority=excluded.priority,
                    deadline=excluded.deadline,
                    metadata=excluded.metadata
                """,
                (
                    goal.id,
                    goal.description,
                    float(goal.priority),
                    deadline_iso,
                    metadata_json,
                ),
            )

    def load_all_goals(self) -> List[Goal]:
        rows = self._conn.execute(
            "SELECT * FROM goals ORDER BY rowid"
        ).fetchall()
        goals: List[Goal] = []
        for r in rows:
            deadline = None
            if r["deadline"]:
                try:
                    deadline = datetime.datetime.fromisoformat(r["deadline"])
                except ValueError:
                    deadline = None
            metadata = {}
            if r["metadata"]:
                try:
                    metadata = json.loads(r["metadata"])
                except json.JSONDecodeError:
                    metadata = {}
            goals.append(
                Goal(
                    id=r["id"],
                    description=r["description"],
                    priority=float(r["priority"]),
                    deadline=deadline,
                    metadata=metadata,
                )
            )
        return goals

    def delete_goal(self, goal_id: str) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM goals WHERE id=?", (goal_id,))

    # ------------------------------------------------------------------
    # Memory – delegated to a SQLiteMemorySystem sharing the DB file.
    # ------------------------------------------------------------------
    def _memory_backend(self):
        """Lazy accessor; we don't import the SQLiteMemorySystem at
        module load to keep the dependency surface tight."""
        from aria_core.memory.sqlite_memory_system import SQLiteMemorySystem
        return SQLiteMemorySystem(self._db_path)

    def save_memory_items(self, items) -> None:
        """Forward to a SQLiteMemorySystem bound to the same DB file."""
        # Local imports keep the goals module free of a hard dependency
        # on the memory package (avoids any potential import cycle).
        from aria_core.memory.models import (
            EpisodicItem,
            SemanticItem,
            WorkingMemoryItem,
        )

        backend = self._memory_backend()
        try:
            for it in items:
                if isinstance(it, WorkingMemoryItem):
                    backend.store_working(it)
                elif isinstance(it, EpisodicItem):
                    backend.store_episodic(it)
                elif isinstance(it, SemanticItem):
                    backend.store_semantic(it)
                else:
                    # Bare MemoryItem → treat as episodic so it's at least
                    # persisted; tests that need strict store semantics
                    # should use a concrete subclass.
                    backend.store_episodic(
                        EpisodicItem(
                            id=it.id,
                            timestamp=it.timestamp,
                            importance=it.importance,
                            metadata=it.metadata,
                        )
                    )
        finally:
            backend.close()

    def load_memory_items(self, *, store: str, limit: int = 1000):
        """Forward to a SQLiteMemorySystem bound to the same DB file."""
        backend = self._memory_backend()
        try:
            if store == "working":
                return backend.get_working(limit=limit)
            if store == "episodic":
                return backend.get_episodic(limit=limit)
            if store == "semantic":
                return backend.get_semantic(limit=limit)
            raise ValueError(f"unknown store: {store}")
        finally:
            backend.close()

    def update_memory_importance(
        self, item_id: str, new_importance: float
    ) -> None:
        backend = self._memory_backend()
        try:
            # Find the current importance to compute a delta; the
            # contract only requires clamping, which
            # SQLiteMemorySystem.update_importance already does after
            # adding the delta.
            row = backend._conn.execute(
                "SELECT importance FROM memory_items WHERE id=?",
                (item_id,),
            ).fetchone()
            if row is None:
                return
            delta = float(new_importance) - float(row["importance"])
            backend.update_importance(item_id, delta)
        finally:
            backend.close()

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.ProgrammingError:
            pass

    def __del__(self) -> None:  # pragma: no cover – best effort
        try:
            self._conn.close()
        except Exception:
            pass