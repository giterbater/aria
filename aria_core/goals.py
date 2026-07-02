# aria_core/goals.py
"""
Goal Manager with subtask decomposition, states, and progress tracking.

Goals are long-lived objects that ARIA maintains across sessions.
Each goal can contain subtasks with dependencies and priorities.
The manager provides relevance lookup and progress computation.
"""

from __future__ import annotations

import datetime
import json
import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from aria_core.persistence.interfaces import PersistenceProtocol

if TYPE_CHECKING:
    from aria_core.memory.models import MemoryItem


class GoalState(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    ABANDONED = "abandoned"
    PAUSED = "paused"


@dataclass
class Subtask:
    """A single step within a goal."""
    id: str = field(default_factory=lambda: str(__import__('uuid').uuid4()))
    description: str = ""
    state: GoalState = GoalState.ACTIVE
    priority: float = 1.0
    depends_on: List[str] = field(default_factory=list)  # subtask IDs
    result: str = ""  # outcome notes
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    completed_at: Optional[datetime.datetime] = None

    def is_ready(self, completed_ids: set[str]) -> bool:
        """Check if all dependencies are satisfied."""
        return all(dep in completed_ids for dep in self.depends_on)


@dataclass
class Goal:
    """A goal with optional subtasks, state, and progress tracking."""
    id: str = field(default_factory=lambda: str(__import__('uuid').uuid4()))
    description: str = ""
    priority: float = 1.0
    deadline: Optional[datetime.datetime] = None
    state: GoalState = GoalState.ACTIVE
    subtasks: List[Subtask] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    updated_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    completed_at: Optional[datetime.datetime] = None

    @property
    def progress(self) -> float:
        """Return completion percentage 0.0–1.0."""
        if not self.subtasks:
            return 1.0 if self.state == GoalState.COMPLETED else 0.0
        done = sum(1 for s in self.subtasks if s.state == GoalState.COMPLETED)
        return done / len(self.subtasks)

    @property
    def is_complete(self) -> bool:
        return self.state == GoalState.COMPLETED

    @property
    def active_subtasks(self) -> List[Subtask]:
        return [s for s in self.subtasks if s.state == GoalState.ACTIVE]

    @property
    def next_subtask(self) -> Subtask | None:
        """Return the highest-priority ready subtask."""
        completed = {s.id for s in self.subtasks if s.state == GoalState.COMPLETED}
        ready = [s for s in self.active_subtasks if s.is_ready(completed)]
        if not ready:
            return None
        ready.sort(key=lambda s: s.priority, reverse=True)
        return ready[0]


class GoalManager:
    """
    Manages goals with subtask decomposition, state transitions,
    and progress tracking. Supports persistence via PersistenceProtocol.
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
            self._goals: List[Goal] = persistence.load_all_goals()
            existing_ids = {g.id for g in self._goals}
            for g in goals or []:
                if g.id not in existing_ids:
                    self._goals.append(g)
                    persistence.save_goal(g)
        else:
            self._goals: List[Goal] = list(goals or [])

    # -----------------------------------------------------------------
    # Goal lifecycle
    # -----------------------------------------------------------------
    def add_goal(self, goal: Goal) -> None:
        self._goals.append(goal)
        if self._persistence is not None:
            self._persistence.save_goal(goal)

    def remove_goal(self, goal_id: str) -> None:
        self._goals = [g for g in self._goals if g.id != goal_id]
        if self._persistence is not None:
            self._persistence.delete_goal(goal_id)

    def get_goal(self, goal_id: str) -> Goal | None:
        for g in self._goals:
            if g.id == goal_id:
                return g
        return None

    def list_goals(self, state: GoalState | None = None) -> List[Goal]:
        if state is None:
            return list(self._goals)
        return [g for g in self._goals if g.state == state]

    # -----------------------------------------------------------------
    # State transitions
    # -----------------------------------------------------------------
    def complete_goal(self, goal_id: str) -> None:
        goal = self.get_goal(goal_id)
        if goal is None:
            return
        goal.state = GoalState.COMPLETED
        goal.completed_at = datetime.datetime.now()
        goal.updated_at = datetime.datetime.now()
        for s in goal.subtasks:
            if s.state == GoalState.ACTIVE:
                s.state = GoalState.COMPLETED
                s.completed_at = datetime.datetime.now()
        self._save(goal)

    def block_goal(self, goal_id: str, reason: str = "") -> None:
        goal = self.get_goal(goal_id)
        if goal is None:
            return
        goal.state = GoalState.BLOCKED
        goal.metadata["block_reason"] = reason
        goal.updated_at = datetime.datetime.now()
        self._save(goal)

    def pause_goal(self, goal_id: str) -> None:
        goal = self.get_goal(goal_id)
        if goal is None:
            return
        goal.state = GoalState.PAUSED
        goal.updated_at = datetime.datetime.now()
        self._save(goal)

    def resume_goal(self, goal_id: str) -> None:
        goal = self.get_goal(goal_id)
        if goal is None:
            return
        goal.state = GoalState.ACTIVE
        goal.updated_at = datetime.datetime.now()
        self._save(goal)

    def abandon_goal(self, goal_id: str, reason: str = "") -> None:
        goal = self.get_goal(goal_id)
        if goal is None:
            return
        goal.state = GoalState.ABANDONED
        goal.metadata["abandon_reason"] = reason
        goal.updated_at = datetime.datetime.now()
        self._save(goal)

    # -----------------------------------------------------------------
    # Subtask management
    # -----------------------------------------------------------------
    def add_subtask(self, goal_id: str, subtask: Subtask) -> None:
        goal = self.get_goal(goal_id)
        if goal is None:
            return
        goal.subtasks.append(subtask)
        goal.updated_at = datetime.datetime.now()
        self._save(goal)

    def complete_subtask(self, goal_id: str, subtask_id: str, result: str = "") -> None:
        goal = self.get_goal(goal_id)
        if goal is None:
            return
        for s in goal.subtasks:
            if s.id == subtask_id:
                s.state = GoalState.COMPLETED
                s.result = result
                s.completed_at = datetime.datetime.now()
                break
        goal.updated_at = datetime.datetime.now()
        if goal.progress >= 1.0:
            goal.state = GoalState.COMPLETED
            goal.completed_at = datetime.datetime.now()
        self._save(goal)

    def fail_subtask(self, goal_id: str, subtask_id: str, reason: str = "") -> None:
        goal = self.get_goal(goal_id)
        if goal is None:
            return
        for s in goal.subtasks:
            if s.id == subtask_id:
                s.state = GoalState.BLOCKED
                s.result = reason
                break
        goal.updated_at = datetime.datetime.now()
        self._save(goal)

    # -----------------------------------------------------------------
    # Relevance and progress
    # -----------------------------------------------------------------
    def relevant_goals(self, cue: str, *, limit: int = 5) -> List[Goal]:
        cue_tokens = set(cue.lower().split())
        scored: List[Goal] = []
        for g in self._goals:
            if g.state in (GoalState.COMPLETED, GoalState.ABANDONED):
                continue
            desc_tokens = set(g.description.lower().split())
            if cue_tokens & desc_tokens:
                scored.append(g)
        scored.sort(key=lambda g: g.priority, reverse=True)
        return scored[:limit]

    def overall_progress(self) -> float:
        active = [g for g in self._goals if g.state == GoalState.ACTIVE]
        if not active:
            return 1.0
        return sum(g.progress for g in active) / len(active)

    def next_action(self) -> tuple[Goal, Subtask] | None:
        """Return the highest-priority goal's next ready subtask."""
        active = [g for g in self._goals if g.state == GoalState.ACTIVE]
        active.sort(key=lambda g: g.priority, reverse=True)
        for goal in active:
            sub = goal.next_subtask
            if sub is not None:
                return (goal, sub)
        return None

    # -----------------------------------------------------------------
    # Persistence helper
    # -----------------------------------------------------------------
    def _save(self, goal: Goal) -> None:
        if self._persistence is not None:
            self._persistence.save_goal(goal)


# ---------------------------------------------------------------------
# SQLite-backed persistence
# ---------------------------------------------------------------------
class SQLiteGoalStore(PersistenceProtocol):
    """SQLite-backed persistence for goals and memory."""

    def __init__(self, db_path):
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.initialize()

    def initialize(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS goals (
                    id TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    priority REAL NOT NULL,
                    deadline TEXT,
                    state TEXT DEFAULT 'active',
                    subtasks TEXT DEFAULT '[]',
                    metadata TEXT DEFAULT '{}',
                    created_at TEXT,
                    updated_at TEXT,
                    completed_at TEXT
                );
                """
            )

    def save_goal(self, goal: Goal) -> None:
        deadline_iso = goal.deadline.isoformat() if goal.deadline else None
        subtasks_json = json.dumps([
            {
                "id": s.id, "description": s.description,
                "state": s.state.value, "priority": s.priority,
                "depends_on": s.depends_on, "result": s.result,
                "created_at": s.created_at.isoformat(),
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            }
            for s in goal.subtasks
        ])
        metadata_json = json.dumps(goal.metadata or {})
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO goals (id, description, priority, deadline, state,
                    subtasks, metadata, created_at, updated_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    description=excluded.description,
                    priority=excluded.priority,
                    deadline=excluded.deadline,
                    state=excluded.state,
                    subtasks=excluded.subtasks,
                    metadata=excluded.metadata,
                    created_at=excluded.created_at,
                    updated_at=excluded.updated_at,
                    completed_at=excluded.completed_at
                """,
                (
                    goal.id, goal.description, float(goal.priority),
                    deadline_iso, goal.state.value, subtasks_json,
                    metadata_json,
                    goal.created_at.isoformat(),
                    goal.updated_at.isoformat(),
                    goal.completed_at.isoformat() if goal.completed_at else None,
                ),
            )

    def load_all_goals(self) -> List[Goal]:
        rows = self._conn.execute("SELECT * FROM goals ORDER BY rowid").fetchall()
        goals: List[Goal] = []
        for r in rows:
            deadline = None
            if r["deadline"]:
                try:
                    deadline = datetime.datetime.fromisoformat(r["deadline"])
                except ValueError:
                    pass

            subtasks = []
            if r["subtasks"]:
                try:
                    for s in json.loads(r["subtasks"]):
                        completed_at = None
                        if s.get("completed_at"):
                            try:
                                completed_at = datetime.datetime.fromisoformat(s["completed_at"])
                            except ValueError:
                                pass
                        subtasks.append(Subtask(
                            id=s["id"], description=s["description"],
                            state=GoalState(s["state"]), priority=s["priority"],
                            depends_on=s.get("depends_on", []),
                            result=s.get("result", ""),
                            created_at=datetime.datetime.fromisoformat(s["created_at"]) if s.get("created_at") else datetime.datetime.now(),
                            completed_at=completed_at,
                        ))
                except (json.JSONDecodeError, KeyError):
                    pass

            metadata = {}
            if r["metadata"]:
                try:
                    metadata = json.loads(r["metadata"])
                except json.JSONDecodeError:
                    pass

            created_at = datetime.datetime.now()
            if r["created_at"]:
                try:
                    created_at = datetime.datetime.fromisoformat(r["created_at"])
                except ValueError:
                    pass

            updated_at = datetime.datetime.now()
            if r["updated_at"]:
                try:
                    updated_at = datetime.datetime.fromisoformat(r["updated_at"])
                except ValueError:
                    pass

            completed_at = None
            if r["completed_at"]:
                try:
                    completed_at = datetime.datetime.fromisoformat(r["completed_at"])
                except ValueError:
                    pass

            goals.append(Goal(
                id=r["id"], description=r["description"],
                priority=float(r["priority"]), deadline=deadline,
                state=GoalState(r["state"]) if r["state"] else GoalState.ACTIVE,
                subtasks=subtasks, metadata=metadata,
                created_at=created_at, updated_at=updated_at,
                completed_at=completed_at,
            ))
        return goals

    def delete_goal(self, goal_id: str) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM goals WHERE id=?", (goal_id,))

    def _memory_backend(self):
        from aria_core.memory.sqlite_memory_system import SQLiteMemorySystem
        return SQLiteMemorySystem(self._db_path)

    def save_memory_items(self, items) -> None:
        from aria_core.memory.models import EpisodicItem, SemanticItem, WorkingMemoryItem
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
                    backend.store_episodic(EpisodicItem(
                        id=it.id, timestamp=it.timestamp,
                        importance=it.importance, metadata=it.metadata,
                    ))
        finally:
            backend.close()

    def load_memory_items(self, *, store: str, limit: int = 1000):
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

    def update_memory_importance(self, item_id: str, new_importance: float) -> None:
        backend = self._memory_backend()
        try:
            row = backend._conn.execute(
                "SELECT importance FROM memory_items WHERE id=?", (item_id,)
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

    def __del__(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
