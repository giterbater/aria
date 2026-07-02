from __future__ import annotations

import datetime
import json
import sqlite3
from pathlib import Path
from typing import List, Optional

from .interfaces import Reflection, Lesson, ReflectionType


class ReflectionStore:
    """SQLite-backed persistence for reflections and lessons."""

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
                CREATE TABLE IF NOT EXISTS reflections (
                    id TEXT PRIMARY KEY,
                    reflection_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    what_worked TEXT DEFAULT '[]',
                    what_failed TEXT DEFAULT '[]',
                    what_to_improve TEXT DEFAULT '[]',
                    context TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS lessons (
                    id TEXT PRIMARY KEY,
                    reflection_id TEXT,
                    text TEXT NOT NULL,
                    reflection_type TEXT NOT NULL,
                    source TEXT DEFAULT '',
                    confidence REAL DEFAULT 1.0,
                    tags TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (reflection_id) REFERENCES reflections(id)
                );
                CREATE TABLE IF NOT EXISTS skill_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    skill_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    duration_ms REAL DEFAULT 0.0,
                    output TEXT DEFAULT '',
                    errors TEXT DEFAULT '[]',
                    warnings TEXT DEFAULT '[]',
                    metadata TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                """
            )

    def save_reflection(self, reflection: Reflection) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO reflections
                    (id, reflection_type, summary, what_worked, what_failed,
                     what_to_improve, context, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reflection.id,
                    reflection.reflection_type.value,
                    reflection.summary,
                    json.dumps(reflection.what_worked),
                    json.dumps(reflection.what_failed),
                    json.dumps(reflection.what_to_improve),
                    json.dumps(reflection.context, default=str),
                    reflection.created_at.isoformat(),
                ),
            )
            for lesson in reflection.lessons:
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO lessons
                        (id, reflection_id, text, reflection_type, source,
                         confidence, tags, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        lesson.id, reflection.id, lesson.text,
                        lesson.reflection_type.value, lesson.source,
                        lesson.confidence, json.dumps(lesson.tags),
                        lesson.created_at.isoformat(),
                    ),
                )

    def load_reflections(self, limit: int = 50) -> List[Reflection]:
        rows = self._conn.execute(
            "SELECT * FROM reflections ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        reflections = []
        for r in rows:
            lesson_rows = self._conn.execute(
                "SELECT * FROM lessons WHERE reflection_id=?",
                (r["id"],),
            ).fetchall()
            lessons = [
                Lesson(
                    id=lr["id"], text=lr["text"],
                    reflection_type=ReflectionType(lr["reflection_type"]),
                    source=lr["source"], confidence=lr["confidence"],
                    tags=json.loads(lr["tags"]),
                    created_at=datetime.datetime.fromisoformat(lr["created_at"]),
                )
                for lr in lesson_rows
            ]
            reflections.append(Reflection(
                id=r["id"],
                reflection_type=ReflectionType(r["reflection_type"]),
                summary=r["summary"],
                what_worked=json.loads(r["what_worked"]),
                what_failed=json.loads(r["what_failed"]),
                what_to_improve=json.loads(r["what_to_improve"]),
                lessons=lessons,
                context=json.loads(r["context"]),
                created_at=datetime.datetime.fromisoformat(r["created_at"]),
            ))
        return reflections

    def load_lessons(self, tags: List[str] | None = None, limit: int = 100) -> List[Lesson]:
        if tags:
            tag_set = set(tags)
            rows = self._conn.execute(
                "SELECT * FROM lessons ORDER BY created_at DESC",
            ).fetchall()
            filtered = [
                r for r in rows
                if tag_set & set(json.loads(r["tags"]))
           ][:limit]
        else:
            filtered = self._conn.execute(
                "SELECT * FROM lessons ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

        return [
            Lesson(
                id=r["id"], text=r["text"],
                reflection_type=ReflectionType(r["reflection_type"]),
                source=r["source"], confidence=r["confidence"],
                tags=json.loads(r["tags"]),
                created_at=datetime.datetime.fromisoformat(r["created_at"]),
            )
            for r in filtered
        ]

    def save_skill_outcome(self, skill_name: str, action: str, success: bool,
                           duration_ms: float = 0.0, output: str = "",
                           errors: list[str] | None = None, warnings: list[str] | None = None,
                           metadata: dict | None = None) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO skill_outcomes
                    (skill_name, action, success, duration_ms, output,
                     errors, warnings, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    skill_name, action, int(success), duration_ms, output,
                    json.dumps(errors or []), json.dumps(warnings or []),
                    json.dumps(metadata or {}),
                    datetime.datetime.now().isoformat(),
                ),
            )

    def get_skill_stats(self, skill_name: str | None = None) -> dict:
        if skill_name:
            rows = self._conn.execute(
                "SELECT success, COUNT(*) as cnt, AVG(duration_ms) as avg_ms "
                "FROM skill_outcomes WHERE skill_name=? GROUP BY success",
                (skill_name,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT skill_name, success, COUNT(*) as cnt, AVG(duration_ms) as avg_ms "
                "FROM skill_outcomes GROUP BY skill_name, success",
            ).fetchall()

        stats = {}
        for r in rows:
            name = r["skill_name"] if "skill_name" in r.keys() else skill_name
            if name not in stats:
                stats[name] = {"success": 0, "failure": 0, "avg_ms": 0.0}
            if r["success"]:
                stats[name]["success"] = r["cnt"]
            else:
                stats[name]["failure"] = r["cnt"]
            stats[name]["avg_ms"] = round(r["avg_ms"] or 0, 1)
        return stats

    def get_success_rate(self, skill_name: str) -> float:
        row = self._conn.execute(
            "SELECT COUNT(*) as total, SUM(success) as ok "
            "FROM skill_outcomes WHERE skill_name=?",
            (skill_name,),
        ).fetchone()
        if row is None or row["total"] == 0:
            return 0.0
        return (row["ok"] or 0) / row["total"]

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.ProgrammingError:
            pass
