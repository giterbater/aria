"""Reasoning benchmark tasks — evaluate planning quality, dependency handling, confidence estimation."""

from __future__ import annotations

from typing import Any

from ..benchmark_result import BenchmarkResult
from ..benchmark_registry import BenchmarkRegistry
from ..metrics import MetricType


def bench_reasoning_planning_quality(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate whether reasoning produces a non-trivial, multi-step plan."""
    context = aria.reasoning._fallback_reason(
        "Analyze codebase structure and identify test gaps",
        __import__("aria_core.reasoning", fromlist=["ReasoningContext"]).ReasoningContext(
            objective="Analyze codebase structure and identify test gaps",
            available_skills=["code", "terminal", "git", "file", "documentation"],
            known_patterns=["scan before modifying"],
            failure_modes=["risky without tests"],
        ),
    )
    has_steps = len(context.steps) >= 2
    has_descriptions = all(s.get("description") for s in context.steps)
    has_skills = all(s.get("skill") for s in context.steps)
    score = 0.0
    if has_steps:
        score += 0.4
    if has_descriptions:
        score += 0.2
    if has_skills:
        score += 0.2
    score += min(0.2, len(context.steps) * 0.05)

    return BenchmarkResult(
        task_name="reasoning_planning_quality",
        category="reasoning",
        success=has_steps,
        score=min(1.0, score),
        confidence=context.confidence.overall,
        details={
            "steps_count": len(context.steps),
            "has_descriptions": has_descriptions,
            "has_skills": has_skills,
        },
    )


def bench_reasoning_dependency_handling(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate whether reasoning produces correct dependency chains."""
    context = aria.reasoning._fallback_reason(
        "Read the code, run tests, and then fix failures",
        __import__("aria_core.reasoning", fromlist=["ReasoningContext"]).ReasoningContext(
            objective="Read the code, run tests, and then fix failures",
            available_skills=["code", "terminal", "file"],
        ),
    )
    plan = context.to_plan()
    dep_count = 0
    for step in plan.steps:
        if step.depends_on:
            valid_deps = all(d in {s.id for s in plan.steps} for d in step.depends_on)
            if valid_deps:
                dep_count += 1

    has_ordering = any(s.depends_on for s in plan.steps)
    score = 0.5 if has_ordering else 0.3
    if dep_count > 0:
        score += min(0.5, dep_count * 0.25)

    return BenchmarkResult(
        task_name="reasoning_dependency_handling",
        category="reasoning",
        success=has_ordering or len(plan.steps) >= 2,
        score=min(1.0, score),
        confidence=context.confidence.overall,
        details={
            "steps_with_deps": dep_count,
            "total_steps": len(plan.steps),
            "has_ordering": has_ordering,
        },
    )


def bench_reasoning_confidence_estimation(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate whether reasoning produces calibrated confidence scores."""
    context = aria.reasoning._fallback_reason(
        "Run the test suite",
        __import__("aria_core.reasoning", fromlist=["ReasoningContext"]).ReasoningContext(
            objective="Run the test suite",
            available_skills=["terminal", "code"],
            known_patterns=["pytest is fast"],
        ),
    )
    conf = context.confidence
    all_populated = all(v > 0 for v in [conf.goal, conf.plan, conf.skill_selection, conf.memory_match])
    overall_valid = 0.0 <= conf.overall <= 1.0
    score = 0.0
    if all_populated:
        score += 0.5
    if overall_valid:
        score += 0.25
    if conf.is_confident:
        score += 0.25

    return BenchmarkResult(
        task_name="reasoning_confidence_estimation",
        category="reasoning",
        success=all_populated and overall_valid,
        score=min(1.0, score),
        confidence=conf.overall,
        details={
            "goal": conf.goal,
            "plan": conf.plan,
            "skill_selection": conf.skill_selection,
            "memory_match": conf.memory_match,
            "overall": conf.overall,
            "is_confident": conf.is_confident,
        },
    )


def bench_reasoning_verification(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate whether reasoning verifies plans before execution."""
    context = aria.reasoning._fallback_reason(
        "Commit changes to git",
        __import__("aria_core.reasoning", fromlist=["ReasoningContext"]).ReasoningContext(
            objective="Commit changes to git",
            available_skills=["git", "terminal"],
        ),
    )
    verified = context.verified
    notes = context.verification_notes
    score = 0.5 if verified else 0.2
    if notes:
        score += min(0.5, len(notes) * 0.1)

    return BenchmarkResult(
        task_name="reasoning_verification",
        category="reasoning",
        success=True,
        score=min(1.0, score),
        confidence=context.confidence.overall,
        details={
            "verified": verified,
            "verification_notes_count": len(notes),
        },
    )


def bench_reasoning_adaptive_replan(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate adaptive replanning from failure."""
    original = aria.reasoning._fallback_reason(
        "Run tests and fix failures",
        __import__("aria_core.reasoning", fromlist=["ReasoningContext"]).ReasoningContext(
            objective="Run tests and fix failures",
            available_skills=["terminal", "code", "file"],
        ),
    )
    if not original.steps:
        return BenchmarkResult(
            task_name="reasoning_adaptive_replan",
            category="reasoning", success=False, score=0.0,
            details={"error": "no original steps"},
        )

    failed_step = original.steps[0].copy()
    failed_step["status"] = "failed"
    replan = aria.reasoning.replan_from_failure(
        original, failed_step, "command timed out"
    )
    has_replan = len(replan.steps) > 0
    has_reasoning = bool(replan.reasoning)
    confidence_dropped = replan.confidence.overall <= original.confidence.overall

    score = 0.0
    if has_replan:
        score += 0.4
    if has_reasoning:
        score += 0.3
    if confidence_dropped:
        score += 0.3

    return BenchmarkResult(
        task_name="reasoning_adaptive_replan",
        category="reasoning",
        success=has_replan,
        score=min(1.0, score),
        confidence=replan.confidence.overall,
        details={
            "original_steps": len(original.steps),
            "replan_steps": len(replan.steps),
            "has_reasoning": has_reasoning,
            "confidence_dropped": confidence_dropped,
        },
    )


def register(registry: BenchmarkRegistry) -> None:
    tasks = [
        ("reasoning_planning_quality", "Evaluate planning quality", bench_reasoning_planning_quality),
        ("reasoning_dependency_handling", "Evaluate dependency handling", bench_reasoning_dependency_handling),
        ("reasoning_confidence_estimation", "Evaluate confidence estimation", bench_reasoning_confidence_estimation),
        ("reasoning_verification", "Evaluate plan verification", bench_reasoning_verification),
        ("reasoning_adaptive_replan", "Evaluate adaptive replanning", bench_reasoning_adaptive_replan),
    ]
    for name, desc, func in tasks:
        registry.register_task(name, "reasoning", desc, func)

    registry.register_suite("reasoning", [t[0] for t in tasks])
