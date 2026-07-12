"""Skills benchmark tasks — evaluate skill execution, routing, retries."""

from __future__ import annotations

from typing import Any

from ..benchmark_result import BenchmarkResult
from ..benchmark_registry import BenchmarkRegistry
from ..metrics import MetricType


def bench_skills_execution_success(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate that skills execute successfully."""
    sm = aria.skills
    result = sm.execute_skill("terminal", command="echo 'benchmark'")
    score = 1.0 if result.success else 0.0

    return BenchmarkResult(
        task_name="skills_execution_success",
        category="skills",
        success=result.success,
        score=score,
        confidence=0.9 if result.success else 0.2,
        details={"output": str(result.output)[:100]},
    )


def bench_skills_routing_accuracy(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate that the skill router selects appropriate skills."""
    sm = aria.skills
    from aria_core.skills.router import SkillRouter
    router = SkillRouter(sm.registry)

    test_cases = [
        ("terminal", "run shell command"),
        ("file", "read a file"),
        ("git", "check git status"),
        ("code", "scan codebase"),
    ]

    correct = 0
    for expected, task_desc in test_cases:
        resolved = router.resolve(task_desc)
        if resolved:
            names = [s.meta.name for s in resolved]
            if expected in names:
                correct += 1

    score = correct / len(test_cases) if test_cases else 0.0

    return BenchmarkResult(
        task_name="skills_routing_accuracy",
        category="skills",
        success=correct >= len(test_cases) * 0.5,
        score=score,
        confidence=0.8,
        details={
            "test_cases": len(test_cases),
            "correct_routings": correct,
        },
    )


def bench_skills_retry_behavior(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate that skill execution handles errors without crashing."""
    sm = aria.skills

    result1 = sm.execute_skill("terminal", command="echo 'success'")
    result2 = sm.execute_skill("terminal", command="exit 1")
    result3 = sm.execute_skill("terminal", command="echo 'recovered'")

    non_crashing = result1 is not None and result2 is not None and result3 is not None
    score = 0.0
    if non_crashing:
        score += 0.5
    if result1.success:
        score += 0.25
    if not result2.success:
        score += 0.25

    return BenchmarkResult(
        task_name="skills_retry_behavior",
        category="skills",
        success=non_crashing,
        score=min(1.0, score),
        confidence=0.85,
        details={
            "first_success": result1.success,
            "second_success": result2.success,
            "third_success": result3.success,
        },
    )


def bench_skills_execution_latency(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate skill execution latency."""
    import time

    sm = aria.skills
    times = []
    for _ in range(5):
        t0 = time.monotonic()
        sm.execute_skill("terminal", command="echo 'bench'")
        elapsed = (time.monotonic() - t0) * 1000
        times.append(elapsed)

    avg_ms = sum(times) / len(times) if times else 0
    fast = avg_ms < 200
    score = 0.0
    if fast:
        score += 0.6
    elif avg_ms < 1000:
        score += 0.3
    if times:
        score += 0.4

    return BenchmarkResult(
        task_name="skills_execution_latency",
        category="skills",
        success=fast,
        score=min(1.0, score),
        confidence=0.8,
        duration_ms=round(avg_ms, 1),
        details={
            "avg_latency_ms": round(avg_ms, 1),
            "min_latency_ms": round(min(times), 1) if times else 0,
            "max_latency_ms": round(max(times), 1) if times else 0,
        },
    )


def bench_skills_registry_integrity(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate that the skill registry is properly populated."""
    sm = aria.skills
    registry = sm.registry

    count = registry.count
    skill_names = [m.name for m in registry.list_skills()]
    expected = ["code", "file", "terminal", "git", "documentation", "web_research"]
    registered_expected = [n for n in expected if n in skill_names]

    score = len(registered_expected) / len(expected) if expected else 0.0

    return BenchmarkResult(
        task_name="skills_registry_integrity",
        category="skills",
        success=len(registered_expected) >= len(expected) * 0.5,
        score=score,
        confidence=0.95,
        details={
            "total_registered": count,
            "expected_found": len(registered_expected),
            "found_names": skill_names,
        },
    )


def register(registry: BenchmarkRegistry) -> None:
    tasks = [
        ("skills_execution_success", "Evaluate skill execution success", bench_skills_execution_success),
        ("skills_routing_accuracy", "Evaluate skill routing accuracy", bench_skills_routing_accuracy),
        ("skills_retry_behavior", "Evaluate retry behavior", bench_skills_retry_behavior),
        ("skills_execution_latency", "Evaluate execution latency", bench_skills_execution_latency),
        ("skills_registry_integrity", "Evaluate registry integrity", bench_skills_registry_integrity),
    ]
    for name, desc, func in tasks:
        registry.register_task(name, "skills", desc, func)

    registry.register_suite("skills", [t[0] for t in tasks])
