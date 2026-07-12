"""Benchmark suites — logical groupings of benchmark tasks."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from .benchmark_registry import BenchmarkRegistry, BenchmarkTaskEntry
from .benchmark_result import BenchmarkResult

logger = logging.getLogger("aria.benchmarks.suite")


@dataclass
class SuiteResult:
    """Aggregated result from running a benchmark suite."""
    suite_name: str
    results: list[BenchmarkResult] = field(default_factory=list)
    total_duration_ms: float = 0.0

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.success)

    @property
    def total_count(self) -> int:
        return len(self.results)

    @property
    def success_rate(self) -> float:
        return self.success_count / self.total_count if self.total_count else 0.0

    @property
    def average_score(self) -> float:
        scores = [r.score for r in self.results]
        return sum(scores) / len(scores) if scores else 0.0

    @property
    def average_confidence(self) -> float:
        confs = [r.confidence for r in self.results if r.confidence > 0]
        return sum(confs) / len(confs) if confs else 0.0

    def to_dict(self) -> dict:
        return {
            "suite_name": self.suite_name,
            "success_rate": self.success_rate,
            "average_score": self.average_score,
            "average_confidence": self.average_confidence,
            "total_duration_ms": self.total_duration_ms,
            "results": [r.to_dict() for r in self.results],
        }


class BenchmarkSuite:
    """Runs a logical group of benchmark tasks against an ARIA instance."""

    def __init__(self, registry: BenchmarkRegistry) -> None:
        self._registry = registry

    def run_suite(
        self,
        suite_name: str,
        aria: Any,
        **kwargs: Any,
    ) -> SuiteResult:
        """Run all tasks in a named suite."""
        tasks = self._registry.get_suite_tasks(suite_name)
        if not tasks:
            logger.warning("Suite '%s' has no tasks", suite_name)
            return SuiteResult(suite_name=suite_name)

        logger.info("Running suite '%s' with %d tasks", suite_name, len(tasks))
        t0 = time.monotonic()
        results = []
        for task in tasks:
            result = self._run_task(task, aria, **kwargs)
            results.append(result)

        total_ms = (time.monotonic() - t0) * 1000
        suite_result = SuiteResult(
            suite_name=suite_name,
            results=results,
            total_duration_ms=round(total_ms, 1),
        )

        logger.info(
            "Suite '%s' complete: %d/%d passed (avg score=%.2f, %.1fms)",
            suite_name, suite_result.success_count, suite_result.total_count,
            suite_result.average_score, total_ms,
        )
        return suite_result

    def run_all(self, aria: Any, **kwargs: Any) -> dict[str, SuiteResult]:
        """Run all registered suites."""
        results = {}
        for suite_name in self._registry.list_suites():
            results[suite_name] = self.run_suite(suite_name, aria, **kwargs)
        return results

    def _run_task(self, task: BenchmarkTaskEntry, aria: Any, **kwargs: Any) -> BenchmarkResult:
        """Execute a single benchmark task and capture its result."""
        t0 = time.monotonic()
        try:
            result = task.func(aria, **kwargs)
            if isinstance(result, BenchmarkResult):
                duration = (time.monotonic() - t0) * 1000
                result.duration_ms = round(duration, 1)
                return result
            else:
                duration = (time.monotonic() - t0) * 1000
                return BenchmarkResult(
                    task_name=task.name,
                    category=task.category,
                    success=True,
                    score=float(result) if isinstance(result, (int, float)) else 1.0,
                    duration_ms=round(duration, 1),
                )
        except Exception as exc:
            duration = (time.monotonic() - t0) * 1000
            logger.error("Task '%s' failed: %s", task.name, exc)
            return BenchmarkResult(
                task_name=task.name,
                category=task.category,
                success=False,
                score=0.0,
                duration_ms=round(duration, 1),
                errors=[str(exc)],
            )
