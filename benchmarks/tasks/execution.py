"""Execution benchmark tasks — evaluate end-to-end objective processing."""

from __future__ import annotations

from typing import Any

from ..benchmark_result import BenchmarkResult
from ..benchmark_registry import BenchmarkRegistry
from ..metrics import MetricType


def bench_execution_full_pipeline(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate the full ARIACore.process_objective pipeline."""
    result = aria.process_objective("check the project structure")

    success = result.get("success", False)
    has_plan = result.get("plan_steps", 0) > 0
    has_confidence = "confidence" in result
    has_duration = result.get("duration_ms", 0) > 0

    score = 0.0
    if success:
        score += 0.4
    if has_plan:
        score += 0.2
    if has_confidence:
        score += 0.2
    if has_duration:
        score += 0.2

    return BenchmarkResult(
        task_name="execution_full_pipeline",
        category="execution",
        success=success,
        score=min(1.0, score),
        confidence=0.85,
        duration_ms=result.get("duration_ms", 0),
        details={
            "plan_steps": result.get("plan_steps", 0),
            "steps_completed": result.get("steps_completed", 0),
            "verified": result.get("verified", False),
        },
    )


def bench_execution_shell_command(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate shell command execution via skills."""
    result = aria.skills.execute_skill("terminal", command="echo 'benchmark_test'")
    score = 1.0 if result.success and "benchmark_test" in str(result.output) else 0.5

    return BenchmarkResult(
        task_name="execution_shell_command",
        category="execution",
        success=result.success,
        score=score,
        confidence=0.9,
        details={"output": str(result.output)[:100]},
    )


def bench_execution_file_operations(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate file skill operations."""
    import tempfile
    import os

    test_file = os.path.join(tempfile.gettempdir(), "aria_bench_test.txt")
    write_result = aria.skills.execute_skill("file", action="write", path=test_file, content="benchmark data")

    read_result = aria.skills.execute_skill("file", action="read", path=test_file) if write_result.success else None

    success = write_result.success and (read_result.success if read_result else False)
    score = 0.0
    if write_result.success:
        score += 0.5
    if read_result and read_result.success:
        score += 0.5

    try:
        os.unlink(test_file)
    except OSError:
        pass

    return BenchmarkResult(
        task_name="execution_file_operations",
        category="execution",
        success=success,
        score=min(1.0, score),
        confidence=0.85,
        details={
            "write_success": write_result.success,
            "read_success": read_result.success if read_result else False,
        },
    )


def bench_execution_git_workflow(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate git skill operations."""
    status_result = aria.skills.execute_skill("git", action="status")
    score = 0.5 if status_result.success else 0.0

    log_result = aria.skills.execute_skill("git", action="log")
    if log_result.success:
        score += 0.5

    return BenchmarkResult(
        task_name="execution_git_workflow",
        category="execution",
        success=status_result.success,
        score=min(1.0, score),
        confidence=0.8,
        details={
            "status_success": status_result.success,
            "log_success": log_result.success,
        },
    )


def bench_execution_objective_processing(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Evaluate that objective processing returns structured results."""
    result = aria.process_objective("scan the repository for code patterns")

    has_objective = "objective" in result
    has_success = "success" in result
    has_plan_steps = "plan_steps" in result
    has_duration = "duration_ms" in result
    has_confidence = "confidence" in result

    required_fields = sum([has_objective, has_success, has_plan_steps, has_duration, has_confidence])
    score = required_fields / 5

    return BenchmarkResult(
        task_name="execution_objective_processing",
        category="execution",
        success=required_fields >= 4,
        score=score,
        confidence=0.9,
        duration_ms=result.get("duration_ms", 0),
        details={
            "fields_present": required_fields,
            "fields": {
                "objective": has_objective,
                "success": has_success,
                "plan_steps": has_plan_steps,
                "duration_ms": has_duration,
                "confidence": has_confidence,
            },
        },
    )


def register(registry: BenchmarkRegistry) -> None:
    tasks = [
        ("execution_full_pipeline", "Evaluate full pipeline", bench_execution_full_pipeline),
        ("execution_shell_command", "Evaluate shell command execution", bench_execution_shell_command),
        ("execution_file_operations", "Evaluate file operations", bench_execution_file_operations),
        ("execution_git_workflow", "Evaluate git workflow", bench_execution_git_workflow),
        ("execution_objective_processing", "Evaluate objective processing", bench_execution_objective_processing),
    ]
    for name, desc, func in tasks:
        registry.register_task(name, "execution", desc, func)

    registry.register_suite("execution", [t[0] for t in tasks])
