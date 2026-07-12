"""Benchmark runner — orchestrates the full benchmark execution lifecycle."""

from __future__ import annotations

import datetime
import logging
import time
import uuid
from typing import Any

from .benchmark_registry import BenchmarkRegistry, get_registry, register_default_tasks
from .benchmark_result import BenchmarkHistory, BenchmarkRun
from .benchmark_suite import BenchmarkSuite, SuiteResult
from .metrics import MetricSet, MetricType
from .report import BenchmarkReport

logger = logging.getLogger("aria.benchmarks.runner")


class BenchmarkRunner:
    """Top-level orchestrator that runs benchmarks and produces reports."""

    def __init__(
        self,
        history_path: str | None = None,
        registry: BenchmarkRegistry | None = None,
    ) -> None:
        self._history = BenchmarkHistory(db_path=history_path or ":memory:")
        self._registry = registry or get_registry()
        if self._registry.count() == 0:
            register_default_tasks()
        self._suite = BenchmarkSuite(self._registry)

    def run(
        self,
        aria: Any,
        *,
        suite: str | None = None,
        version: str = "1.0.0",
        metadata: dict[str, Any] | None = None,
    ) -> BenchmarkRun:
        """Run benchmarks against an ARIA instance.

        Args:
            aria: The ARIACore instance to benchmark.
            suite: Specific suite name, or None for all suites.
            version: ARIA version string for tracking.
            metadata: Additional metadata to attach to the run.
        """
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.datetime.now().isoformat()

        logger.info("Starting benchmark run %s", run_id)
        t0 = time.monotonic()

        suite_results: dict[str, SuiteResult]
        if suite:
            sr = self._suite.run_suite(suite, aria)
            suite_results = {suite: sr}
        else:
            suite_results = self._suite.run_all(aria)

        all_results = []
        for sr in suite_results.values():
            all_results.extend(sr.results)

        metrics = self._compute_metrics(all_results, run_id, timestamp)
        total_ms = (time.monotonic() - t0) * 1000

        run = BenchmarkRun(
            run_id=run_id,
            timestamp=timestamp,
            aria_version=version,
            results=all_results,
            metrics=metrics,
            metadata={
                **(metadata or {}),
                "total_duration_ms": round(total_ms, 1),
                "suites_run": list(suite_results.keys()),
                "suite_summaries": {k: v.to_dict() for k, v in suite_results.items()},
            },
        )

        self._history.save_run(run)
        logger.info(
            "Benchmark run %s complete: overall=%.1f, tasks=%d/%d, %.0fms",
            run_id, run.overall_score, run.successful_tasks, run.total_tasks, total_ms,
        )
        return run

    def _compute_metrics(self, results: list, run_id: str, timestamp: str) -> MetricSet:
        metrics = MetricSet(run_id=run_id, timestamp=timestamp)

        category_scores: dict[str, list[float]] = {}
        category_success: dict[str, list[bool]] = {}
        category_confidence: dict[str, list[float]] = {}
        category_latency: dict[str, list[float]] = {}

        for r in results:
            category_scores.setdefault(r.category, []).append(r.score)
            category_success.setdefault(r.category, []).append(r.success)
            if r.confidence > 0:
                category_confidence.setdefault(r.category, []).append(r.confidence)
            if r.duration_ms > 0:
                category_latency.setdefault(r.category, []).append(r.duration_ms)

        import statistics

        type_map = {
            "reasoning": MetricType.REASONING,
            "planning": MetricType.PLANNING,
            "language": MetricType.LANGUAGE,
            "memory": MetricType.MEMORY,
            "skills": MetricType.SKILLS,
            "reflection": MetricType.REFLECTION,
            "learning": MetricType.LEARNING,
            "execution": MetricType.EXECUTION,
            "simulation": MetricType.SIMULATION,
        }

        for cat, scores in category_scores.items():
            mt = type_map.get(cat, MetricType.OVERALL)
            avg_score = statistics.mean(scores) if scores else 0.0
            conf_list = category_confidence.get(cat, [])
            avg_conf = statistics.mean(conf_list) if conf_list else 0.0
            lat_list = category_latency.get(cat, [])
            avg_lat = statistics.mean(lat_list) if lat_list else 0.0
            success_list = category_success.get(cat, [])
            success_rate = sum(success_list) / len(success_list) if success_list else 0.0

            metrics.add(f"{cat}_score", avg_score, mt)
            metrics.add(f"{cat}_success_rate", success_rate, mt, unit="%")
            metrics.add(f"{cat}_confidence", avg_conf, mt)
            metrics.add(f"{cat}_latency", avg_lat, mt, unit="ms")

        total_tasks = len(results)
        successful = sum(1 for r in results if r.success)
        all_confidences = [r.confidence for r in results if r.confidence > 0]
        all_latencies = [r.duration_ms for r in results if r.duration_ms > 0]

        metrics.add("task_success_rate", successful / total_tasks if total_tasks else 0.0, MetricType.OVERALL)
        metrics.add("average_confidence", statistics.mean(all_confidences) if all_confidences else 0.0, MetricType.OVERALL)
        metrics.add("average_latency", statistics.mean(all_latencies) if all_latencies else 0.0, MetricType.OVERALL, unit="ms")
        metrics.add("total_tasks", float(total_tasks), MetricType.OVERALL)

        retry_count = sum(1 for r in results if r.details.get("retried"))
        metrics.add("retry_rate", retry_count / total_tasks if total_tasks else 0.0, MetricType.OVERALL)

        memory_hits = sum(1 for r in results if r.category == "memory" and r.details.get("hit"))
        memory_total = sum(1 for r in results if r.category == "memory")
        metrics.add("memory_hit_rate", memory_hits / memory_total if memory_total else 0.0, MetricType.MEMORY)

        return metrics

    def compare(self, run_id_a: str, run_id_b: str) -> dict:
        return self._history.compare_runs(run_id_a, run_id_b)

    def latest_run(self) -> BenchmarkRun | None:
        return self._history.latest_run()

    def best_run(self) -> BenchmarkRun | None:
        return self._history.best_run()

    def trend(self, last_n: int = 10) -> list[dict]:
        return self._history.performance_trend(last_n)

    def regression(self, baseline_id: str | None = None, threshold: float = -5.0) -> dict:
        return self._history.regression_report(baseline_id, threshold)

    def export_json(self, path: str) -> None:
        self._history.export_json(path)

    def export_markdown(self, path: str) -> None:
        self._history.export_markdown(path)

    def report(self, run: BenchmarkRun | None = None) -> BenchmarkReport:
        if run is None:
            run = self._history.latest_run()
        if run is None:
            raise ValueError("No benchmark run available")
        prev = None
        runs = self._history.all_runs(limit=2)
        if len(runs) >= 2:
            prev = runs[1]
        return BenchmarkReport(run, previous=prev)

    @property
    def history(self) -> BenchmarkHistory:
        return self._history

    @property
    def registry(self) -> BenchmarkRegistry:
        return self._registry
