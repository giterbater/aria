from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class CognitiveMetrics:
    """Trackable metrics for cognitive performance evaluation."""
    decision_accuracy: float = 0.0
    planning_accuracy: float = 0.0
    execution_success: float = 0.0
    recovery_success: float = 0.0
    reflection_quality: float = 0.0
    learning_effectiveness: float = 0.0
    confidence_calibration: float = 0.0
    curiosity_usage: float = 0.0
    memory_relevance: float = 0.0
    overall_score: float = 0.0

    def compute_overall(self) -> float:
        weights = {
            "decision_accuracy": 0.15,
            "planning_accuracy": 0.15,
            "execution_success": 0.20,
            "recovery_success": 0.10,
            "reflection_quality": 0.10,
            "learning_effectiveness": 0.10,
            "confidence_calibration": 0.10,
            "curiosity_usage": 0.05,
            "memory_relevance": 0.05,
        }
        total = 0.0
        for field_name, weight in weights.items():
            total += getattr(self, field_name) * weight
        self.overall_score = total
        return total

    def summary(self) -> str:
        return (
            f"Decision: {self.decision_accuracy:.0%} | "
            f"Planning: {self.planning_accuracy:.0%} | "
            f"Execution: {self.execution_success:.0%} | "
            f"Recovery: {self.recovery_success:.0%} | "
            f"Overall: {self.overall_score:.0%}"
        )


class MetricsTracker:
    """Persists and tracks cognitive metrics across sessions."""

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
                CREATE TABLE IF NOT EXISTS benchmark_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    benchmark_name TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    state_enabled INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def record_run(self, benchmark_name: str, metrics: CognitiveMetrics, state_enabled: bool) -> None:
        import datetime
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO benchmark_runs (benchmark_name, metrics_json, state_enabled, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    benchmark_name,
                    json.dumps({
                        "decision_accuracy": metrics.decision_accuracy,
                        "planning_accuracy": metrics.planning_accuracy,
                        "execution_success": metrics.execution_success,
                        "recovery_success": metrics.recovery_success,
                        "reflection_quality": metrics.reflection_quality,
                        "learning_effectiveness": metrics.learning_effectiveness,
                        "confidence_calibration": metrics.confidence_calibration,
                        "curiosity_usage": metrics.curiosity_usage,
                        "memory_relevance": metrics.memory_relevance,
                        "overall_score": metrics.overall_score,
                    }),
                    int(state_enabled),
                    datetime.datetime.now().isoformat(),
                ),
            )

    def get_comparison(self, benchmark_name: str) -> dict:
        rows = self._conn.execute(
            "SELECT * FROM benchmark_runs WHERE benchmark_name=? ORDER BY created_at",
            (benchmark_name,),
        ).fetchall()

        without = []
        with_state = []
        for r in rows:
            data = json.loads(r["metrics_json"])
            if r["state_enabled"]:
                with_state.append(data)
            else:
                without.append(data)

        def avg(lst, key):
            if not lst:
                return 0.0
            return sum(d[key] for d in lst) / len(lst)

        return {
            "benchmark": benchmark_name,
            "runs_without_state": len(without),
            "runs_with_state": len(with_state),
            "without_state": {k: round(avg(without, k), 3) for k in without[0]} if without else {},
            "with_state": {k: round(avg(with_state, k), 3) for k in with_state[0]} if with_state else {},
        }

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.ProgrammingError:
            pass
