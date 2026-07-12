"""Benchmark result types and historical run persistence."""

from __future__ import annotations

import datetime
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .metrics import MetricSet, MetricType


@dataclass
class BenchmarkResult:
    """Result of a single benchmark task execution."""
    task_name: str
    category: str
    success: bool
    score: float
    duration_ms: float = 0.0
    confidence: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "task_name": self.task_name,
            "category": self.category,
            "success": self.success,
            "score": self.score,
            "duration_ms": self.duration_ms,
            "confidence": self.confidence,
            "details": self.details,
            "errors": self.errors,
        }


@dataclass
class BenchmarkRun:
    """Complete result of a benchmark run across all suites."""
    run_id: str = ""
    timestamp: str = ""
    aria_version: str = "1.0.0"
    results: list[BenchmarkResult] = field(default_factory=list)
    metrics: MetricSet = field(default_factory=MetricSet)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def overall_score(self) -> float:
        metrics_score = self.metrics.overall_score()
        if metrics_score > 0:
            return metrics_score
        if not self.results:
            return 0.0
        scores = [r.score for r in self.results]
        return sum(scores) / len(scores) if scores else 0.0

    @property
    def total_tasks(self) -> int:
        return len(self.results)

    @property
    def successful_tasks(self) -> int:
        return sum(1 for r in self.results if r.success)

    @property
    def task_success_rate(self) -> float:
        return self.successful_tasks / self.total_tasks if self.total_tasks else 0.0

    def category_score(self, category: str) -> float:
        scores = [r.score for r in self.results if r.category == category]
        return sum(scores) / len(scores) if scores else 0.0

    def category_success_rate(self, category: str) -> float:
        cat_results = [r for r in self.results if r.category == category]
        if not cat_results:
            return 0.0
        return sum(1 for r in cat_results if r.success) / len(cat_results)

    def average_confidence(self) -> float:
        confidences = [r.confidence for r in self.results if r.confidence > 0]
        return sum(confidences) / len(confidences) if confidences else 0.0

    def average_latency(self) -> float:
        durations = [r.duration_ms for r in self.results if r.duration_ms > 0]
        return sum(durations) / len(durations) if durations else 0.0

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "aria_version": self.aria_version,
            "overall_score": self.overall_score,
            "task_success_rate": self.task_success_rate,
            "total_tasks": self.total_tasks,
            "successful_tasks": self.successful_tasks,
            "average_confidence": self.average_confidence(),
            "average_latency": self.average_latency(),
            "category_scores": {
                cat: self.category_score(cat)
                for cat in sorted(set(r.category for r in self.results))
            },
            "results": [r.to_dict() for r in self.results],
            "metrics": self.metrics.to_dict(),
            "metadata": self.metadata,
        }


class BenchmarkHistory:
    """Persistent storage for benchmark run history."""

    def __init__(self, db_path: str = ":memory:"):
        self._db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        with self._conn:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS benchmark_runs (
                    run_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    aria_version TEXT DEFAULT '1.0.0',
                    overall_score REAL DEFAULT 0.0,
                    task_success_rate REAL DEFAULT 0.0,
                    total_tasks INTEGER DEFAULT 0,
                    successful_tasks INTEGER DEFAULT 0,
                    average_confidence REAL DEFAULT 0.0,
                    average_latency REAL DEFAULT 0.0,
                    category_scores TEXT DEFAULT '{}',
                    results_json TEXT DEFAULT '[]',
                    metrics_json TEXT DEFAULT '{}',
                    metadata_json TEXT DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_runs_timestamp
                    ON benchmark_runs(timestamp);
                CREATE INDEX IF NOT EXISTS idx_runs_score
                    ON benchmark_runs(overall_score DESC);
            """)

    def save_run(self, run: BenchmarkRun) -> None:
        cat_scores = {cat: run.category_score(cat) for cat in
                      sorted(set(r.category for r in run.results))}
        with self._conn:
            self._conn.execute(
                """INSERT OR REPLACE INTO benchmark_runs
                    (run_id, timestamp, aria_version, overall_score, task_success_rate,
                     total_tasks, successful_tasks, average_confidence, average_latency,
                     category_scores, results_json, metrics_json, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (run.run_id, run.timestamp, run.aria_version,
                 run.overall_score, run.task_success_rate,
                 run.total_tasks, run.successful_tasks,
                 run.average_confidence(), run.average_latency(),
                 json.dumps(cat_scores),
                 json.dumps([r.to_dict() for r in run.results]),
                 json.dumps(run.metrics.to_dict()),
                 json.dumps(run.metadata)),
            )

    def load_run(self, run_id: str) -> BenchmarkRun | None:
        row = self._conn.execute(
            "SELECT * FROM benchmark_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        return self._row_to_run(row) if row else None

    def latest_run(self) -> BenchmarkRun | None:
        row = self._conn.execute(
            "SELECT * FROM benchmark_runs ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        return self._row_to_run(row) if row else None

    def best_run(self) -> BenchmarkRun | None:
        row = self._conn.execute(
            "SELECT * FROM benchmark_runs ORDER BY overall_score DESC LIMIT 1"
        ).fetchone()
        return self._row_to_run(row) if row else None

    def all_runs(self, limit: int = 100) -> list[BenchmarkRun]:
        rows = self._conn.execute(
            "SELECT * FROM benchmark_runs ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_run(r) for r in rows]

    def performance_trend(self, last_n: int = 10) -> list[dict]:
        rows = self._conn.execute(
            """SELECT run_id, timestamp, overall_score, task_success_rate,
                      average_confidence, average_latency, category_scores
               FROM benchmark_runs ORDER BY timestamp DESC LIMIT ?""",
            (last_n,),
        ).fetchall()
        return [
            {
                "run_id": r["run_id"],
                "timestamp": r["timestamp"],
                "overall_score": r["overall_score"],
                "task_success_rate": r["task_success_rate"],
                "average_confidence": r["average_confidence"],
                "average_latency": r["average_latency"],
                "category_scores": json.loads(r["category_scores"]),
            }
            for r in rows
        ]

    def compare_runs(self, run_id_a: str, run_id_b: str) -> dict:
        run_a = self.load_run(run_id_a)
        run_b = self.load_run(run_id_b)
        if not run_a or not run_b:
            return {"error": "One or both runs not found"}

        cats_a = {r.category: [] for r in run_a.results}
        cats_b = {r.category: [] for r in run_b.results}
        for r in run_a.results:
            cats_a[r.category].append(r.score)
        for r in run_b.results:
            cats_b[r.category].append(r.score)

        all_cats = sorted(set(list(cats_a.keys()) + list(cats_b.keys())))
        comparisons = {}
        for cat in all_cats:
            avg_a = sum(cats_a.get(cat, [])) / len(cats_a[cat]) if cats_a.get(cat) else 0.0
            avg_b = sum(cats_b.get(cat, [])) / len(cats_b[cat]) if cats_b.get(cat) else 0.0
            delta = avg_b - avg_a
            comparisons[cat] = {
                "run_a": round(avg_a, 2),
                "run_b": round(avg_b, 2),
                "delta": round(delta, 2),
                "improved": delta > 0,
            }

        return {
            "run_a": {"id": run_id_a, "timestamp": run_a.timestamp, "score": run_a.overall_score},
            "run_b": {"id": run_id_b, "timestamp": run_b.timestamp, "score": run_b.overall_score},
            "overall_delta": round(run_b.overall_score - run_a.overall_score, 2),
            "category_comparisons": comparisons,
        }

    def regression_report(self, baseline_id: str | None = None, threshold: float = -5.0) -> dict:
        runs = self.all_runs(limit=20)
        if len(runs) < 2:
            return {"status": "insufficient_data", "runs_available": len(runs)}

        latest = runs[0]
        if baseline_id:
            baseline = self.load_run(baseline_id)
        else:
            baseline = runs[1] if len(runs) > 1 else latest

        if not baseline:
            return {"status": "baseline_not_found"}

        regressions = []
        cats_latest = {}
        cats_baseline = {}
        for r in latest.results:
            cats_latest.setdefault(r.category, []).append(r.score)
        for r in baseline.results:
            cats_baseline.setdefault(r.category, []).append(r.score)

        for cat in sorted(set(list(cats_latest.keys()) + list(cats_baseline.keys()))):
            avg_l = sum(cats_latest.get(cat, [])) / len(cats_latest[cat]) if cats_latest.get(cat) else 0.0
            avg_b = sum(cats_baseline.get(cat, [])) / len(cats_baseline[cat]) if cats_baseline.get(cat) else 0.0
            delta = avg_l - avg_b
            if delta < threshold:
                regressions.append({
                    "category": cat,
                    "baseline_score": round(avg_b, 2),
                    "latest_score": round(avg_l, 2),
                    "delta": round(delta, 2),
                })

        overall_delta = latest.overall_score - baseline.overall_score
        has_overall_regression = overall_delta < threshold

        return {
            "status": "ok",
            "baseline_run_id": baseline.run_id,
            "latest_run_id": latest.run_id,
            "overall_delta": round(overall_delta, 2),
            "regressions": regressions,
            "has_regression": len(regressions) > 0 or has_overall_regression,
        }

    def export_json(self, path: str) -> None:
        runs = self.all_runs()
        data = [r.to_dict() for r in runs]
        Path(path).write_text(json.dumps(data, indent=2))

    def export_markdown(self, path: str) -> None:
        runs = self.all_runs()
        lines = ["# ARIA Benchmark History\n"]
        for run in runs:
            lines.append(f"## Run {run.run_id} ({run.timestamp})\n")
            lines.append(f"- **Overall Score**: {run.overall_score:.1f}")
            lines.append(f"- **Task Success Rate**: {run.task_success_rate:.1%}")
            lines.append(f"- **Average Confidence**: {run.average_confidence():.2f}")
            lines.append(f"- **Average Latency**: {run.average_latency():.1f}ms")
            lines.append(f"- **Tasks**: {run.successful_tasks}/{run.total_tasks}")
            lines.append("")
            cat_scores = {}
            for r in run.results:
                cat_scores.setdefault(r.category, []).append(r.score)
            lines.append("| Category | Score |")
            lines.append("|----------|-------|")
            for cat, scores in sorted(cat_scores.items()):
                avg = sum(scores) / len(scores) if scores else 0
                lines.append(f"| {cat} | {avg:.1f} |")
            lines.append("")
        Path(path).write_text("\n".join(lines))

    def export_html(self, path: str) -> None:
        runs = self.all_runs()
        latest = runs[0] if runs else BenchmarkRun(run_id="empty", timestamp="")
        previous = runs[1] if len(runs) > 1 else None
        from .report import BenchmarkReport

        html = BenchmarkReport(latest, previous=previous).to_html(title="ARIA Benchmark History")
        Path(path).write_text(html, encoding="utf-8")

    def _row_to_run(self, row: sqlite3.Row) -> BenchmarkRun:
        results_data = json.loads(row["results_json"])
        results = [BenchmarkResult(**r) for r in results_data]

        metrics_data = json.loads(row["metrics_json"])
        metrics = MetricSet(
            run_id=metrics_data.get("run_id", ""),
            timestamp=metrics_data.get("timestamp", ""),
        )
        for m in metrics_data.get("metrics", []):
            from .metrics import MetricType as MT
            metrics.add(
                name=m["name"], value=m["value"],
                metric_type=MT(m["metric_type"]),
                unit=m.get("unit", ""),
                **m.get("details", {}),
            )

        return BenchmarkRun(
            run_id=row["run_id"],
            timestamp=row["timestamp"],
            aria_version=row["aria_version"],
            results=results,
            metrics=metrics,
            metadata=json.loads(row["metadata_json"]),
        )

    def close(self) -> None:
        self._conn.close()
