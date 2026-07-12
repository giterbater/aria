"""Memory benchmark tasks — evaluate retrieval, recall, relevance scoring."""

from __future__ import annotations

from typing import Any

from ..benchmark_result import BenchmarkResult
from ..benchmark_registry import BenchmarkRegistry
from ..metrics import MetricType


def bench_memory_retrieval_accuracy(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate whether memory retrieves relevant items for a query."""
    from aria_core.memory.models import EpisodicItem, WorkingMemoryItem

    mem = aria.memory
    items = [
        WorkingMemoryItem(importance=0.8, context={"topic": "testing", "action": "run_tests"}),
        WorkingMemoryItem(importance=0.6, context={"topic": "git", "action": "commit"}),
        WorkingMemoryItem(importance=0.5, context={"topic": "code", "action": "scan"}),
    ]
    for item in items:
        mem.store_working(item)

    retrieved = mem.retrieve_relevant("run the test suite", limit=3)
    has_results = len(retrieved) > 0
    has_scores = all(score > 0 for _, score in retrieved) if retrieved else False

    score = 0.0
    if has_results:
        score += 0.5
    if has_scores:
        score += 0.3
    if len(retrieved) >= 2:
        score += 0.2

    return BenchmarkResult(
        task_name="memory_retrieval_accuracy",
        category="memory",
        success=has_results,
        score=min(1.0, score),
        confidence=0.75,
        details={
            "items_stored": len(items),
            "items_retrieved": len(retrieved),
            "has_relevance_scores": has_scores,
            "hit": has_results,
        },
    )


def bench_memory_recall_latency(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate memory recall performance."""
    import time

    mem = aria.memory
    from aria_core.memory.models import WorkingMemoryItem
    for i in range(20):
        mem.store_working(WorkingMemoryItem(
            importance=0.5 + (i * 0.02),
            context={"topic": f"topic_{i}", "action": f"action_{i}"},
        ))

    t0 = time.monotonic()
    results = mem.retrieve_relevant("topic_10", limit=5)
    elapsed_ms = (time.monotonic() - t0) * 1000

    fast = elapsed_ms < 100
    score = 0.0
    if fast:
        score += 0.6
    elif elapsed_ms < 500:
        score += 0.3
    if len(results) > 0:
        score += 0.4

    return BenchmarkResult(
        task_name="memory_recall_latency",
        category="memory",
        success=fast,
        score=min(1.0, score),
        confidence=0.8,
        duration_ms=elapsed_ms,
        details={
            "latency_ms": round(elapsed_ms, 2),
            "items_returned": len(results),
            "is_fast": fast,
        },
    )


def bench_memory_relevance_scoring(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate that relevance scores are ordered and meaningful."""
    from aria_core.memory.models import WorkingMemoryItem

    mem = aria.memory
    items = [
        WorkingMemoryItem(importance=0.9, context={"topic": "testing pytest unittest"}),
        WorkingMemoryItem(importance=0.3, context={"topic": "design ui color"}),
        WorkingMemoryItem(importance=0.7, context={"topic": "testing integration"}),
    ]
    for item in items:
        mem.store_working(item)

    results = mem.retrieve_relevant("testing", limit=3)
    if len(results) < 2:
        return BenchmarkResult(
            task_name="memory_relevance_scoring",
            category="memory", success=False, score=0.3,
            details={"items_retrieved": len(results)},
        )

    scores = [s for _, s in results]
    ordered = all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))

    score = 0.0
    if ordered:
        score += 0.6
    else:
        score += 0.3
    if len(results) >= 2:
        score += 0.4

    return BenchmarkResult(
        task_name="memory_relevance_scoring",
        category="memory",
        success=True,
        score=min(1.0, score),
        confidence=0.7,
        details={
            "results_count": len(results),
            "scores_ordered": ordered,
            "scores": [round(s, 3) for s in scores],
        },
    )


def bench_memory_episodic_recall(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate episodic memory storage and retrieval."""
    from aria_core.memory.models import EpisodicItem, Outcome

    mem = aria.memory
    episodes = [
        EpisodicItem(
            importance=0.8,
            structured_input={"objective": "run tests"},
            decision={"skill": "terminal"},
            outcome=Outcome.SUCCESS.value,
            notes="Tests passed",
        ),
        EpisodicItem(
            importance=0.4,
            structured_input={"objective": "fix bug"},
            decision={"skill": "file"},
            outcome=Outcome.FAILED.value,
            notes="Could not reproduce",
        ),
    ]
    for ep in episodes:
        mem.store_episodic(ep)

    stored = mem.get_episodic(limit=10)
    has_episodes = len(stored) > 0

    score = 0.0
    if has_episodes:
        score += 0.5
    if len(stored) >= 2:
        score += 0.3
    if any(ep.outcome for ep in stored):
        score += 0.2

    return BenchmarkResult(
        task_name="memory_episodic_recall",
        category="memory",
        success=has_episodes,
        score=min(1.0, score),
        confidence=0.75,
        details={
            "episodes_stored": len(episodes),
            "episodes_retrieved": len(stored),
        },
    )


def bench_memory_semantic_recall(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate semantic memory storage and retrieval."""
    from aria_core.memory.models import SemanticItem

    mem = aria.memory
    items = [
        SemanticItem(importance=0.9, fact="pytest is the preferred test runner", confidence=0.95),
        SemanticItem(importance=0.6, fact="SQLite is used for persistence", confidence=0.8),
    ]
    for item in items:
        mem.store_semantic(item)

    retrieved = mem.get_semantic(query="test runner", limit=5)
    has_items = len(retrieved) > 0

    score = 0.0
    if has_items:
        score += 0.5
    if len(retrieved) >= 1:
        score += 0.3
    if any(s.confidence > 0 for s in retrieved):
        score += 0.2

    return BenchmarkResult(
        task_name="memory_semantic_recall",
        category="memory",
        success=has_items,
        score=min(1.0, score),
        confidence=0.7,
        details={
            "items_stored": len(items),
            "items_retrieved": len(retrieved),
        },
    )


def register(registry: BenchmarkRegistry) -> None:
    tasks = [
        ("memory_retrieval_accuracy", "Evaluate retrieval accuracy", bench_memory_retrieval_accuracy),
        ("memory_recall_latency", "Evaluate recall latency", bench_memory_recall_latency),
        ("memory_relevance_scoring", "Evaluate relevance scoring", bench_memory_relevance_scoring),
        ("memory_episodic_recall", "Evaluate episodic recall", bench_memory_episodic_recall),
        ("memory_semantic_recall", "Evaluate semantic recall", bench_memory_semantic_recall),
    ]
    for name, desc, func in tasks:
        registry.register_task(name, "memory", desc, func)

    registry.register_suite("memory", [t[0] for t in tasks])
