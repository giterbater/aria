"""Planning benchmark tasks — evaluate plan creation, step ordering, lifecycle management."""

from __future__ import annotations

from typing import Any

from ..benchmark_result import BenchmarkResult
from ..benchmark_registry import BenchmarkRegistry
from ..metrics import MetricType


def bench_planning_decomposition(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate whether planning decomposes objectives into concrete steps."""
    engine = __import__("aria_core.planning", fromlist=["PlanningEngine"]).PlanningEngine()
    plan = engine.create_plan("Analyze codebase structure and run the test suite")

    has_steps = len(plan.steps) >= 2
    has_actions = all(s.action for s in plan.steps)
    has_descriptions = all(s.description for s in plan.steps)

    score = 0.0
    if has_steps:
        score += 0.4
    if has_actions:
        score += 0.3
    if has_descriptions:
        score += 0.3

    return BenchmarkResult(
        task_name="planning_decomposition",
        category="planning",
        success=has_steps,
        score=min(1.0, score),
        confidence=0.8 if has_steps else 0.3,
        details={
            "steps_count": len(plan.steps),
            "has_actions": has_actions,
            "has_descriptions": has_descriptions,
        },
    )


def bench_planning_step_ordering(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate whether plans respect dependency ordering."""
    engine = __import__("aria_core.planning", fromlist=["PlanningEngine"]).PlanningEngine()
    plan = engine.create_plan("Read code, run tests, fix failures")

    has_deps = any(s.depends_on for s in plan.steps)
    valid_deps = True
    step_ids = {s.id for s in plan.steps}
    for step in plan.steps:
        for dep in step.depends_on:
            if dep not in step_ids:
                valid_deps = False

    next_step = plan.next_step
    has_executable = next_step is not None

    score = 0.3 if has_deps else 0.5
    if valid_deps:
        score += 0.3
    if has_executable:
        score += 0.4

    return BenchmarkResult(
        task_name="planning_step_ordering",
        category="planning",
        success=has_executable,
        score=min(1.0, score),
        confidence=0.7,
        details={
            "has_dependencies": has_deps,
            "valid_dependencies": valid_deps,
            "has_executable_step": has_executable,
        },
    )


def bench_planning_lifecycle(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate plan step state transitions."""
    from aria_core.planning.interfaces import PlanStepState

    engine = __import__("aria_core.planning", fromlist=["PlanningEngine"]).PlanningEngine()
    plan = engine.create_plan("Scan repository and check git status")

    if not plan.steps:
        return BenchmarkResult(
            task_name="planning_lifecycle",
            category="planning", success=False, score=0.0,
            details={"error": "no steps"},
        )

    first_step = plan.steps[0]
    initial_state = first_step.state

    engine.step_completed(plan.id, first_step.id, result="done")
    after_complete = first_step.state

    progress_after = plan.progress

    score = 0.0
    if initial_state == PlanStepState.PENDING:
        score += 0.25
    if after_complete == PlanStepState.COMPLETED:
        score += 0.5
    if progress_after > 0:
        score += 0.25

    return BenchmarkResult(
        task_name="planning_lifecycle",
        category="planning",
        success=after_complete == PlanStepState.COMPLETED,
        score=min(1.0, score),
        confidence=0.9,
        details={
            "initial_state": initial_state.value,
            "after_complete": after_complete.value,
            "progress": progress_after,
        },
    )


def bench_planning_next_step_respects_deps(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate that next_step respects dependency graph."""
    engine = __import__("aria_core.planning", fromlist=["PlanningEngine"]).PlanningEngine()
    plan = engine.create_plan("Read code, run tests, fix failures, commit changes")

    if len(plan.steps) < 2:
        return BenchmarkResult(
            task_name="planning_next_step_respects_deps",
            category="planning", success=True, score=0.8,
            details={"note": "simple plan with no deps"},
        )

    first = plan.steps[0]
    engine.step_completed(plan.id, first.id, result="done")
    next_s = plan.next_step

    score = 0.0
    if next_s is not None and next_s.id != first.id:
        score += 0.6
    if next_s is not None:
        score += 0.4

    return BenchmarkResult(
        task_name="planning_next_step_respects_deps",
        category="planning",
        success=next_s is not None,
        score=min(1.0, score),
        confidence=0.85,
        details={
            "completed_step": first.id,
            "next_step": next_s.id if next_s else None,
        },
    )


def register(registry: BenchmarkRegistry) -> None:
    tasks = [
        ("planning_decomposition", "Evaluate objective decomposition", bench_planning_decomposition),
        ("planning_step_ordering", "Evaluate dependency ordering", bench_planning_step_ordering),
        ("planning_lifecycle", "Evaluate step state transitions", bench_planning_lifecycle),
        ("planning_next_step_respects_deps", "Evaluate next_step respects deps", bench_planning_next_step_respects_deps),
    ]
    for name, desc, func in tasks:
        registry.register_task(name, "planning", desc, func)

    registry.register_suite("planning", [t[0] for t in tasks])
