# Milestone 2 — Interface Contract (frozen for this milestone)

This contract is **frozen for Milestone 2**. Any change requires PM review.

---

## 1. Persistence Protocol (new)

**File**: `aria_core/persistence/interfaces.py`

```python
from typing import Protocol, runtime_checkable
from pathlib import Path

@runtime_checkable
class PersistenceProtocol(Protocol):
    """Backend-agnostic on-disk storage used by memory and goals.

    All methods are synchronous; backend implementations may use any
    underlying technology (SQLite, JSON files, etc.). Concurrency is
    the backend's responsibility.
    """

    def initialize(self) -> None:
        """Create tables/files if missing. Idempotent."""

    def save_goal(self, goal: "Goal") -> None:
        """Upsert a goal by id."""

    def load_all_goals(self) -> list["Goal"]:
        """Return every persisted goal in insertion order."""

    def delete_goal(self, goal_id: str) -> None:
        """No-op if the id is absent."""

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
```

---

## 2. ActionExecutor Protocol (new)

**File**: `aria_core/execution/interfaces.py`

```python
from typing import Protocol, runtime_checkable
from dataclasses import dataclass

@dataclass(frozen=True)
class ActionResult:
    success: bool
    message: str
    data: dict | None = None  # tool-specific structured return

@runtime_checkable
class ActionExecutor(Protocol):
    """Executes an ARIA decision in the world and returns the outcome."""

    def execute(self, *, tool_name: str, tool_args: dict) -> ActionResult:
        """Run the named tool. Must not raise; must return ActionResult."""
```

---

## 3. Tool Registry (new)

**File**: `aria_core/execution/registry.py`

The four MVP tools Mimo must ship:

| tool_name | tool_args (typed) | Behavior |
|-----------|-------------------|----------|
| `launch_application` | `{"app": str}` | Windows: `subprocess.Popen(["cmd", "/c", "start", "", app])`. macOS: `subprocess.Popen(["open", "-a", app])`. Linux: `subprocess.Popen([app])`. Fallback `ActionResult(success=False, message=f"unsupported platform: {sys.platform}")`. |
| `set_reminder` | `{"seconds": int, "message": str}` | Use `threading.Timer(seconds, callback)`. `callback` writes to an in-memory `PendingReminders` singleton. Returns `ActionResult(success=True, message=f"reminder set for {seconds}s")`. Worker polls the singleton each turn. |
| `cancel_reminder` | `{"message": str}` | Cancels any pending timer whose message contains the substring. Returns `ActionResult(success=True, message="cancelled N reminder(s)")`. |
| `current_time` | `{}` | Returns `ActionResult(success=True, message=now_iso, data={"iso": str, "epoch": int})`. |

Mimo must also export `class ToolRegistry` with `register(name, fn)`, `dispatch(name, args) -> ActionResult`, and `known_tools() -> list[str]`.

---

## 4. Outcome enum + writeback (changes to existing)

**File**: `aria_core/memory/models.py` (add, do not break existing fields)

```python
from enum import Enum

class Outcome(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    IGNORED = "ignored"
    CORRECTED = "corrected"
```

**File**: `aria_core/memory/interfaces.py` (extend `MemorySystemProtocol`)

Add:
```python
def record_outcome(
    self,
    episode_id: str,
    outcome: "Outcome",
    *,
    notes: str | None = None,
) -> None:
    """Update the outcome field of an existing episodic item.

    No-op if episode_id is unknown. The clamped importance after a
    success is item.importance + 0.1 (capped at 1.0). After a failure
    it is item.importance - 0.05 (floored at 0.0). PARTIAL is +0.0.
    CORRECTED is +0.05. IGNORED is -0.05.
    """
```

This **extends** the existing `MemorySystemProtocol`. Implementations that don't support writeback must raise `NotImplementedError` until M2 lands.

---

## 5. SQLite implementation (new)

**File**: `aria_core/memory/sqlite_memory_system.py`

- Implements `MemorySystemProtocol` (full conformance with the existing contract including `record_outcome`).
- Constructor: `SQLiteMemorySystem(db_path: str | Path = ":memory:")`.
- Uses stdlib `sqlite3` only. No SQLAlchemy.
- Schema (one table per store + one for episodic-outcome):

```sql
CREATE TABLE IF NOT EXISTS memory_items (
    id TEXT PRIMARY KEY,
    store TEXT NOT NULL,           -- 'working' | 'episodic' | 'semantic'
    subtype TEXT NOT NULL,         -- 'WorkingMemoryItem' | ...
    timestamp TEXT NOT NULL,
    importance REAL NOT NULL,
    payload TEXT NOT NULL,         -- JSON blob of dataclass fields
    outcome TEXT,                  -- episodic only
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_store_ts ON memory_items(store, timestamp DESC);
CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    priority REAL NOT NULL,
    deadline TEXT,
    metadata TEXT                  -- JSON blob
);
```

- `payload` is JSON containing all dataclass fields except `id`, `timestamp`, `importance`. On load, Mimo must dispatch on `subtype` and reconstruct the correct concrete type (use `dataclasses.fields()` and a small switch).
- Importance must be clamped to [0, 1] on both write and update.

---

## 6. Goal store (extend existing)

**File**: `aria_core/goals.py`

Add `class SQLiteGoalStore` that uses `PersistenceProtocol`. Do not break the existing `GoalManager` in-memory API. New constructor pattern:

```python
class GoalManager:
    def __init__(self, goals=None, *, persistence: PersistenceProtocol | None = None):
        ...
```

If `persistence` is provided, every `add_goal` / `remove_goal` calls through to the backend. `list_goals()` and `relevant_goals()` remain memory-backed but are loaded from persistence on construction.

---

## 7. What Mimo does NOT touch

- `main.py`, `text_mode_loop.py` (PM owns)
- `input_interpreter/`, `language_cortex/`, `output_planner/`, `ui/` (Nemotron)
- `event_bus.py`, `aria_logging.py` (PM)
- The `aria_core/interfaces.py` dataclasses — Mimo adds new things, doesn't change existing

---

## 8. Test requirements (Mimo writes)

- `tests/test_persistence_sqlite.py` — round-trip 50 episodes, restore goals, importance clamping, missing-id no-ops, subtype preservation across load
- `tests/test_action_executor.py` — each of the four tools, plus a stub executor for tests
- `tests/test_outcome_writeback.py` — importance delta per outcome enum value, clamping, missing-id no-op
- `tests/test_memory_sqlite.py` — `SQLiteMemorySystem` full protocol conformance + persistence round-trip + `record_outcome` integration
- `tests/test_goals_sqlite.py` — `GoalManager(persistence=...)` round-trip

All new tests must run alongside the existing 56 without regression.

---

## 9. Acceptance criteria for M2 (Mimo's portion)

1. `python -m unittest discover -s tests` reports 56 + Mimo's new tests, all green.
2. `from aria_core.memory.sqlite_memory_system import SQLiteMemorySystem` works against `:memory:` and a real file path.
3. `from aria_core.execution.registry import ToolRegistry` works; `launch_application("notepad")` opens Notepad on Windows; `set_reminder(5, "test")` schedules a timer; `current_time()` returns ISO + epoch.
4. `record_outcome(ep_id, Outcome.SUCCESS)` raises the item's importance by 0.1 (clamped); `Outcome.FAILED` drops it by 0.05.
5. No changes to `event_bus.py`, `main.py`, `text_mode_loop.py`, `input_interpreter/`, `language_cortex/`, `output_planner/`, `ui/`.

---

## 10. Git hygiene

- One commit per logical change (interface contract first, then sqlite memory, then goal store, then tools, then tests).
- Co-authored-by line on every commit.
- No modifications outside `aria_core/` except `tests/` and the contract doc itself.