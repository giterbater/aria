from __future__ import annotations

import datetime
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class SkillProfile:
    """Tracked performance data for a single skill."""
    name: str
    total_calls: int = 0
    successes: int = 0
    failures: int = 0
    avg_duration_ms: float = 0.0
    last_used: datetime.datetime | None = None
    best_context: str = ""
    worst_context: str = ""
    confidence: float = 0.5

    @property
    def success_rate(self) -> float:
        return self.successes / self.total_calls if self.total_calls > 0 else 0.0

    @property
    def reliability(self) -> float:
        if self.total_calls < 3:
            return 0.5
        return self.success_rate * min(1.0, self.total_calls / 10)

    def record_use(self, success: bool, duration_ms: float, context: str = "") -> None:
        self.total_calls += 1
        if success:
            self.successes += 1
        else:
            self.failures += 1
        self.avg_duration_ms = (
            (self.avg_duration_ms * (self.total_calls - 1) + duration_ms) / self.total_calls
        )
        self.last_used = datetime.datetime.now()
        if success and context:
            self.best_context = context
        elif not success and context:
            self.worst_context = context
        self.confidence = self.reliability


class SkillTracker:
    """Tracks skill performance across sessions.

    Provides data for the decision engine to choose the best skill
    for a given task based on historical performance.
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
                CREATE TABLE IF NOT EXISTS skill_profiles (
                    name TEXT PRIMARY KEY,
                    total_calls INTEGER DEFAULT 0,
                    successes INTEGER DEFAULT 0,
                    failures INTEGER DEFAULT 0,
                    avg_duration_ms REAL DEFAULT 0.0,
                    last_used TEXT,
                    best_context TEXT DEFAULT '',
                    worst_context TEXT DEFAULT '',
                    confidence REAL DEFAULT 0.5
                );
                """
            )

    def record(self, skill_name: str, success: bool, duration_ms: float = 0.0, context: str = "") -> None:
        row = self._conn.execute(
            "SELECT * FROM skill_profiles WHERE name=?", (skill_name,)
        ).fetchone()

        if row:
            total = row["total_calls"] + 1
            successes = row["successes"] + (1 if success else 0)
            failures = row["failures"] + (0 if success else 1)
            avg_ms = (row["avg_duration_ms"] * row["total_calls"] + duration_ms) / total
            best = context if success else row["best_context"]
            worst = context if not success else row["worst_context"]
            rate = successes / total
            reliability = rate * min(1.0, total / 10) if total >= 3 else 0.5

            with self._conn:
                self._conn.execute(
                    "UPDATE skill_profiles SET total_calls=?, successes=?, failures=?, "
                    "avg_duration_ms=?, last_used=?, best_context=?, worst_context=?, "
                    "confidence=? WHERE name=?",
                    (total, successes, failures, avg_ms,
                     datetime.datetime.now().isoformat(), best, worst,
                     reliability, skill_name),
                )
        else:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO skill_profiles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (skill_name, 1, 1 if success else 0, 0 if success else 1,
                     duration_ms, datetime.datetime.now().isoformat(),
                     context if success else "", context if not success else "",
                     0.5),
                )

    def get_profile(self, skill_name: str) -> SkillProfile | None:
        row = self._conn.execute(
            "SELECT * FROM skill_profiles WHERE name=?", (skill_name,)
        ).fetchone()
        if row is None:
            return None
        return SkillProfile(
            name=row["name"],
            total_calls=row["total_calls"],
            successes=row["successes"],
            failures=row["failures"],
            avg_duration_ms=row["avg_duration_ms"],
            last_used=datetime.datetime.fromisoformat(row["last_used"]) if row["last_used"] else None,
            best_context=row["best_context"],
            worst_context=row["worst_context"],
            confidence=row["confidence"],
        )

    def get_all_profiles(self) -> List[SkillProfile]:
        rows = self._conn.execute(
            "SELECT * FROM skill_profiles ORDER BY confidence DESC"
        ).fetchall()
        return [SkillProfile(
            name=r["name"], total_calls=r["total_calls"],
            successes=r["successes"], failures=r["failures"],
            avg_duration_ms=r["avg_duration_ms"],
            last_used=datetime.datetime.fromisoformat(r["last_used"]) if r["last_used"] else None,
            best_context=r["best_context"], worst_context=r["worst_context"],
            confidence=r["confidence"],
        ) for r in rows]

    def get_best_skill(self, task_keywords: list[str] | None = None) -> str | None:
        """Recommend the best skill based on reliability and task keywords."""
        profiles = self.get_all_profiles()
        if not profiles:
            return None

        if task_keywords:
            task_set = set(k.lower() for k in task_keywords)
            scored = []
            for p in profiles:
                name_match = 1.0 if p.name.lower() in task_set else 0.0
                context_match = 0.5 if any(k in p.best_context.lower() for k in task_set) else 0.0
                score = p.reliability * 0.6 + name_match * 0.2 + context_match * 0.2
                scored.append((p.name, score))
            scored.sort(key=lambda x: x[1], reverse=True)
            return scored[0][0] if scored else None

        return max(profiles, key=lambda p: p.reliability).name

    def get_unreliable_skills(self, threshold: float = 0.3) -> List[SkillProfile]:
        return [p for p in self.get_all_profiles() if p.confidence < threshold and p.total_calls >= 3]

    def get_slow_skills(self, threshold_ms: float = 5000) -> List[SkillProfile]:
        return [p for p in self.get_all_profiles() if p.avg_duration_ms > threshold_ms]

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.ProgrammingError:
            pass
