"""Reflection benchmark tasks — evaluate lesson generation, consistency, actionable recommendations."""

from __future__ import annotations

from typing import Any

from ..benchmark_result import BenchmarkResult
from ..benchmark_registry import BenchmarkRegistry
from ..metrics import MetricType


def bench_reflection_lesson_generation(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate that reflection produces meaningful lessons."""
    reflection = aria.reflection

    r1 = reflection.reflect(
        action="benchmark_lesson_test",
        result="The approach worked well, tests passed",
        context={"test": True},
    )

    has_summary = bool(r1.summary)
    has_lessons = len(r1.lessons) > 0
    has_type = r1.reflection_type is not None

    score = 0.0
    if has_type:
        score += 0.3
    if has_summary:
        score += 0.3
    if has_lessons:
        score += 0.4

    return BenchmarkResult(
        task_name="reflection_lesson_generation",
        category="reflection",
        success=has_type,
        score=min(1.0, score),
        confidence=0.8,
        details={
            "reflection_type": r1.reflection_type.value,
            "has_summary": has_summary,
            "lessons_count": len(r1.lessons),
        },
    )


def bench_reflection_consistency(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate that reflection is consistent across similar inputs."""
    reflection = aria.reflection

    r1 = reflection.reflect(
        action="benchmark_consistency_success",
        result="success: all tests passed",
        context={"test": True},
    )
    r2 = reflection.reflect(
        action="benchmark_consistency_success_2",
        result="success: operation completed",
        context={"test": True},
    )

    types_match = r1.reflection_type == r2.reflection_type

    score = 0.0
    if types_match:
        score += 0.5
    if r1.reflection_type.value in ("success", "improvement"):
        score += 0.25
    if r2.reflection_type.value in ("success", "improvement"):
        score += 0.25

    return BenchmarkResult(
        task_name="reflection_consistency",
        category="reflection",
        success=True,
        score=min(1.0, score),
        confidence=0.75,
        details={
            "type_1": r1.reflection_type.value,
            "type_2": r2.reflection_type.value,
            "types_match": types_match,
        },
    )


def bench_reflection_actionable_recommendations(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate that reflection summary produces actionable recommendations."""
    reflection = aria.reflection

    for i in range(3):
        reflection.reflect(
            action=f"benchmark_rec_test_{i}",
            result="success" if i % 2 == 0 else "error: timeout",
            context={"test": True},
        )

    summary = reflection.get_summary()
    has_recommendations = len(summary.recommendations) > 0
    has_insights = len(summary.recent_insights) > 0
    has_patterns = len(summary.top_patterns) > 0

    score = 0.0
    if has_recommendations:
        score += 0.4
    if has_insights:
        score += 0.3
    if has_patterns:
        score += 0.3

    return BenchmarkResult(
        task_name="reflection_actionable_recommendations",
        category="reflection",
        success=True,
        score=min(1.0, score),
        confidence=0.75,
        details={
            "recommendations_count": len(summary.recommendations),
            "insights_count": len(summary.recent_insights),
            "patterns_count": len(summary.top_patterns),
        },
    )


def bench_reflection_success_failure_tracking(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate that reflection correctly categorizes outcomes."""
    reflection = aria.reflection

    r_success = reflection.reflect(
        action="benchmark_sf_success",
        result="success: tests passed",
        context={"test": True},
    )
    r_failure = reflection.reflect(
        action="benchmark_sf_failure",
        result="error: command failed with traceback",
        context={"test": True},
    )

    score = 0.0
    if r_success.reflection_type.value == "success":
        score += 0.5
    if r_failure.reflection_type.value == "failure":
        score += 0.5

    return BenchmarkResult(
        task_name="reflection_success_failure_tracking",
        category="reflection",
        success=True,
        score=min(1.0, score),
        confidence=0.8,
        details={
            "success_type": r_success.reflection_type.value,
            "failure_type": r_failure.reflection_type.value,
        },
    )


def bench_reflection_summary_quality(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate the quality and completeness of reflection summaries."""
    reflection = aria.reflection

    for i in range(5):
        reflection.reflect(
            action=f"benchmark_summary_{i}",
            result="success" if i % 3 != 0 else "error: failure",
            context={"test": True},
        )

    summary = reflection.get_summary()
    has_total = summary.total_reflections > 0
    has_successes = summary.successes > 0
    has_skill_rates = len(summary.skill_success_rates) > 0

    score = 0.0
    if has_total:
        score += 0.3
    if has_successes:
        score += 0.3
    if summary.failures > 0:
        score += 0.2
    if summary.recent_insights:
        score += 0.2

    return BenchmarkResult(
        task_name="reflection_summary_quality",
        category="reflection",
        success=has_total,
        score=min(1.0, score),
        confidence=0.8,
        details={
            "total_reflections": summary.total_reflections,
            "successes": summary.successes,
            "failures": summary.failures,
            "recent_insights_count": len(summary.recent_insights),
        },
    )


def register(registry: BenchmarkRegistry) -> None:
    tasks = [
        ("reflection_lesson_generation", "Evaluate lesson generation", bench_reflection_lesson_generation),
        ("reflection_consistency", "Evaluate reflection consistency", bench_reflection_consistency),
        ("reflection_actionable_recommendations", "Evaluate actionable recommendations", bench_reflection_actionable_recommendations),
        ("reflection_success_failure_tracking", "Evaluate success/failure tracking", bench_reflection_success_failure_tracking),
        ("reflection_summary_quality", "Evaluate summary quality", bench_reflection_summary_quality),
    ]
    for name, desc, func in tasks:
        registry.register_task(name, "reflection", desc, func)

    registry.register_suite("reflection", [t[0] for t in tasks])
