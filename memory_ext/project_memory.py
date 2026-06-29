from __future__ import annotations

import datetime
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Union


class ProjectMemorySQLite:
    """SQLite-backed project memory for the CTO agent.

    Uses a single ``project_memory`` table with a ``category`` column
    to distinguish between decisions, roadmap items, specialist profiles,
    and codebase facts.
    """

    def __init__(self, db_path: Union[str, Path] = ":memory:") -> None:
        self._db_path = str(db_path)
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._counter = 0
        self.initialize()

    def initialize(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS project_memory (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_pm_category
                    ON project_memory(category, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_pm_key
                    ON project_memory(category, key);
                """
            )

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

    def _insert(self, category: str, key: str, value: dict | str) -> None:
        self._counter += 1
        now = f"{datetime.datetime.now().isoformat()}-{self._counter:012d}"
        value_str = json.dumps(value, default=str, ensure_ascii=False) if isinstance(value, dict) else str(value)
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO project_memory (id, category, key, value, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET value=excluded.value
                """,
                (str(uuid.uuid4()), category, key, value_str, now),
            )

    def _query(self, category: str, key: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if key:
            rows = self._conn.execute(
                "SELECT * FROM project_memory WHERE category=? AND key=? "
                "ORDER BY created_at DESC LIMIT ?",
                (category, key, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM project_memory WHERE category=? "
                "ORDER BY created_at DESC LIMIT ?",
                (category, limit),
            ).fetchall()
        results = []
        for r in rows:
            try:
                value = json.loads(r["value"])
            except (json.JSONDecodeError, TypeError):
                value = r["value"]
            results.append({
                "id": r["id"],
                "key": r["key"],
                "value": value,
                "created_at": r["created_at"],
            })
        return results

    def store_decision(self, decision: dict) -> None:
        key = decision.get("action", "unknown")
        self._insert("decision", key, decision)

    def get_recent_decisions(self, limit: int = 20) -> list[dict]:
        return self._query("decision", limit=limit)

    def store_roadmap_item(self, item: dict) -> None:
        item_id = item.get("id", str(uuid.uuid4()))
        item["id"] = item_id
        self._insert("roadmap", item_id, item)

    def get_roadmap(self) -> list[dict]:
        items = self._query("roadmap", limit=500)
        for item in items:
            value = item.get("value", {})
            if isinstance(value, dict):
                item.update(value)
        return items

    def update_roadmap_status(self, item_id: str, status: str) -> None:
        now = datetime.datetime.now().isoformat()
        with self._conn:
            row = self._conn.execute(
                "SELECT value FROM project_memory WHERE category='roadmap' AND key=?",
                (item_id,),
            ).fetchone()
            if row:
                try:
                    value = json.loads(row["value"])
                except (json.JSONDecodeError, TypeError):
                    value = {}
                value["status"] = status
                self._conn.execute(
                    "UPDATE project_memory SET value=? WHERE category='roadmap' AND key=?",
                    (json.dumps(value, default=str), item_id),
                )

    def store_specialist_profile(self, name: str, strengths: list[str]) -> None:
        self._insert("specialist", name, {"name": name, "strengths": strengths})

    def get_specialist_profiles(self) -> dict[str, list[str]]:
        rows = self._query("specialist", limit=100)
        profiles: dict[str, list[str]] = {}
        for r in rows:
            value = r.get("value", {})
            if isinstance(value, dict):
                profiles[value.get("name", r["key"])] = value.get("strengths", [])
        return profiles

    def record_specialist_outcome(self, name: str, success: bool) -> None:
        now = datetime.datetime.now().isoformat()
        with self._conn:
            row = self._conn.execute(
                "SELECT value FROM project_memory WHERE category='specialist' AND key=?",
                (name,),
            ).fetchone()
            if row:
                try:
                    value = json.loads(row["value"])
                except (json.JSONDecodeError, TypeError):
                    value = {"name": name, "strengths": []}
            else:
                value = {"name": name, "strengths": []}

            successes = value.get("successes", 0)
            failures = value.get("failures", 0)
            if success:
                value["successes"] = successes + 1
            else:
                value["failures"] = failures + 1

            self._insert("specialist", name, value)

    def store_codebase_fact(self, key: str, value: str) -> None:
        self._insert("codebase_fact", key, value)

    def get_codebase_facts(self, query: str | None = None) -> list[tuple[str, str]]:
        rows = self._query("codebase_fact", limit=500)
        results = [(r["key"], r["value"]) for r in rows]
        if query:
            q = query.lower()
            results = [(k, v) for k, v in results if q in k.lower() or q in v.lower()]
        return results
