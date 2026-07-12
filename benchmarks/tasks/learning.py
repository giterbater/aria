"""Learning benchmark tasks — evaluate knowledge growth, reuse, pattern recognition."""

from __future__ import annotations

from typing import Any

from ..benchmark_result import BenchmarkResult
from ..benchmark_registry import BenchmarkRegistry
from ..metrics import MetricType


def bench_learning_knowledge_growth(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate that knowledge base grows through reflection processing."""
    from aria_core.learning.knowledge import KnowledgeEntry, KnowledgeType

    kb = aria.knowledge
    initial_count = kb.count()

    entry = KnowledgeEntry(
        knowledge_type=KnowledgeType.FACT,
        key="benchmark_test_fact",
        value="This is a benchmark test fact for measuring knowledge growth",
        confidence=0.9,
        tags=["benchmark", "test"],
    )
    kb.store(entry)
    new_count = kb.count()

    grew = new_count > initial_count
    score = 1.0 if grew else 0.0

    return BenchmarkResult(
        task_name="learning_knowledge_growth",
        category="learning",
        success=grew,
        score=score,
        confidence=0.9,
        details={
            "initial_count": initial_count,
            "after_count": new_count,
            "grew": grew,
        },
    )


def bench_learning_successful_reuse(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate that knowledge entries can be retrieved for reuse."""
    from aria_core.learning.knowledge import KnowledgeEntry, KnowledgeType

    kb = aria.knowledge
    entry = KnowledgeEntry(
        knowledge_type=KnowledgeType.SUCCESS_STRATEGY,
        key="benchmark_reuse_strategy",
        value="Always run tests before committing changes",
        confidence=0.95,
        tags=["strategy", "benchmark"],
    )
    kb.store(entry)

    results = kb.search("benchmark reuse strategy")
    found = len(results) > 0
    score = 0.0
    if found:
        score += 0.6
        kb.record_use(results[0].id)
        updated = kb.get(results[0].key)
        if updated and updated.use_count > 0:
            score += 0.4

    return BenchmarkResult(
        task_name="learning_successful_reuse",
        category="learning",
        success=found,
        score=min(1.0, score),
        confidence=0.85,
        details={
            "found": found,
            "use_count": updated.use_count if found and updated else 0,
        },
    )


def bench_learning_pattern_recognition(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate that the reflection engine identifies patterns."""
    reflection = aria.reflection

    reflection.reflect(
        action="benchmark_pattern_test",
        result="success",
        context={"benchmark": True},
    )
    reflection.reflect(
        action="benchmark_pattern_test_2",
        result="success",
        context={"benchmark": True},
    )

    patterns = reflection.get_learned_patterns()
    has_patterns = len(patterns) > 0

    score = 0.0
    if has_patterns:
        score += 0.5
    if "success" in patterns:
        score += 0.3
    if patterns.get("success", 0) >= 2:
        score += 0.2

    return BenchmarkResult(
        task_name="learning_pattern_recognition",
        category="learning",
        success=has_patterns,
        score=min(1.0, score),
        confidence=0.75,
        details={
            "patterns_found": len(patterns),
            "top_patterns": dict(list(patterns.items())[:5]),
        },
    )


def bench_learning_improvement_across_runs(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate that repeated processing shows improvement."""
    from aria_core.learning.knowledge import KnowledgeEntry, KnowledgeType

    kb = aria.knowledge
    reflection = aria.reflection

    reflection.reflect(
        action="benchmark_improvement_1",
        result="success",
        context={"iteration": 1},
    )
    summary_1 = reflection.get_summary()
    count_1 = summary_1.total_reflections

    reflection.reflect(
        action="benchmark_improvement_2",
        result="success",
        context={"iteration": 2},
    )
    summary_2 = reflection.get_summary()
    count_2 = summary_2.total_reflections

    grew = count_2 > count_1
    score = 0.0
    if grew:
        score += 0.5
    if summary_2.successes > 0:
        score += 0.3
    if summary_2.total_reflections > 0:
        score += 0.2

    return BenchmarkResult(
        task_name="learning_improvement_across_runs",
        category="learning",
        success=grew,
        score=min(1.0, score),
        confidence=0.7,
        details={
            "reflections_after_first": count_1,
            "reflections_after_second": count_2,
            "successes": summary_2.successes,
        },
    )


def bench_learning_skill_tracking(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate that skill performance is tracked."""
    from aria_core.reflection.interfaces import SkillOutcome

    reflection = aria.reflection

    for i in range(5):
        outcome = SkillOutcome(
            skill_name="terminal",
            action="execute",
            success=True,
            duration_ms=50.0 + i * 10,
            output=f"benchmark run {i}",
        )
        reflection.reflect_skill(outcome)

    stats = reflection.get_skill_stats("terminal")
    has_stats = bool(stats)
    score = 0.0
    if has_stats:
        score += 0.5
        total = stats.get("success", 0) + stats.get("failure", 0)
        if total >= 5:
            score += 0.3
        if stats.get("success", 0) > 0:
            score += 0.2

    return BenchmarkResult(
        task_name="learning_skill_tracking",
        category="learning",
        success=has_stats,
        score=min(1.0, score),
        confidence=0.8,
        details={
            "has_stats": has_stats,
            "stats": stats if has_stats else {},
        },
    )


def register(registry: BenchmarkRegistry) -> None:
    tasks = [
        ("learning_knowledge_growth", "Evaluate knowledge growth", bench_learning_knowledge_growth),
        ("learning_successful_reuse", "Evaluate knowledge reuse", bench_learning_successful_reuse),
        ("learning_pattern_recognition", "Evaluate pattern recognition", bench_learning_pattern_recognition),
        ("learning_improvement_across_runs", "Evaluate improvement across runs", bench_learning_improvement_across_runs),
        ("learning_skill_tracking", "Evaluate skill tracking", bench_learning_skill_tracking),
    ]
    for name, desc, func in tasks:
        registry.register_task(name, "learning", desc, func)

    registry.register_suite("learning", [t[0] for t in tasks])
