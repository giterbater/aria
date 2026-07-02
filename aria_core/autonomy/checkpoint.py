from __future__ import annotations

import datetime
import json
import sqlite3
from pathlib import Path
from typing import Any, List

from .task import Task, TaskState, TaskResult


class CheckpointStore:
    """Persistent checkpoint storage for tasks.

    Saves task state at each step so tasks can resume
    after crashes or restarts.
    """

    def __init__(self, db_path: str | Path = ":memory:"):
        self._db_path = str(db_path)
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.initialize()

    def initialize(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    state TEXT NOT NULL,
                    priority REAL DEFAULT 1.0,
                    steps TEXT DEFAULT '[]',
                    current_step INTEGER DEFAULT 0,
                    result TEXT,
                    metadata TEXT DEFAULT '{}',
                    tags TEXT DEFAULT '[]',
                    dependencies TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    updated_at TEXT NOT NULL,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    last_error TEXT DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    step_index INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    checkpoint_data TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                );
                """
            )

    def save_task(self, task: Task) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO tasks
                    (id, name, description, state, priority, steps, current_step,
                     result, metadata, tags, dependencies, created_at, started_at,
                     completed_at, updated_at, retry_count, max_retries, last_error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id, task.name, task.description, task.state.value,
                    task.priority, json.dumps(task.steps), task.current_step,
                    json.dumps({"success": task.result.success, "output": str(task.result.output)[:500], "error": task.result.error}) if task.result else None,
                    json.dumps(task.metadata), json.dumps(task.tags),
                    json.dumps(task.dependencies),
                    task.created_at.isoformat(),
                    task.started_at.isoformat() if task.started_at else None,
                    task.completed_at.isoformat() if task.completed_at else None,
                    task.updated_at.isoformat(),
                    task.retry_count, task.max_retries, task.last_error,
                ),
            )

    def load_task(self, task_id: str) -> Task | None:
        row = self._conn.execute(
            "SELECT * FROM tasks WHERE id=?", (task_id,)
        ).fetchone()
        return self._row_to_task(row) if row else None

    def load_resumable_tasks(self) -> List[Task]:
        """Load tasks that were running or pending (can be resumed)."""
        rows = self._conn.execute(
            "SELECT * FROM tasks WHERE state IN ('running', 'pending', 'paused') "
            "ORDER BY priority DESC, created_at ASC"
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def load_all_tasks(self, limit: int = 50) -> List[Task]:
        rows = self._conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def save_checkpoint(self, task_id: str, step_index: int, state: str, data: dict) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO checkpoints (task_id, step_index, state, checkpoint_data, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (task_id, step_index, state, json.dumps(data), datetime.datetime.now().isoformat()),
            )

    def get_checkpoints(self, task_id: str) -> List[dict]:
        rows = self._conn.execute(
            "SELECT * FROM checkpoints WHERE task_id=? ORDER BY step_index",
            (task_id,),
        ).fetchall()
        return [
            {
                "step_index": r["step_index"],
                "state": r["state"],
                "data": json.loads(r["checkpoint_data"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def get_last_checkpoint(self, task_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM checkpoints WHERE task_id=? ORDER BY step_index DESC LIMIT 1",
            (task_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "step_index": row["step_index"],
            "state": row["state"],
            "data": json.loads(row["checkpoint_data"]),
            "created_at": row["created_at"],
        }

    def delete_task(self, task_id: str) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM checkpoints WHERE task_id=?", (task_id,))
            self._conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM tasks").fetchone()
        return row[0] if row else 0

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.ProgrammingError:
            pass

    def _row_to_task(self, row: sqlite3.Row) -> Task:
        result = None
        if row["result"]:
            try:
                r = json.loads(row["result"])
                result = TaskResult(
                    success=r.get("success", False),
                    output=r.get("output", ""),
                    error=r.get("error", ""),
                )
            except (json.JSONDecodeError, KeyError):
                pass

        return Task(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            state=TaskState(row["state"]),
            priority=row["priority"],
            steps=json.loads(row["steps"]),
            current_step=row["current_step"],
            result=result,
            metadata=json.loads(row["metadata"]),
            tags=json.loads(row["tags"]),
            dependencies=json.loads(row["dependencies"]),
            created_at=datetime.datetime.fromisoformat(row["created_at"]),
            started_at=datetime.datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            updated_at=datetime.datetime.fromisoformat(row["updated_at"]),
            retry_count=row["retry_count"],
            max_retries=row["max_retries"],
            last_error=row["last_error"],
        )
