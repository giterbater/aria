"""Benchmark tasks for ARIA World civilization simulation."""

from __future__ import annotations

import time
from typing import Any

from benchmarks.benchmark_result import BenchmarkResult


def bench_simulation_survival_rate(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Run a simulation and measure agent survival rate."""
    from aria_world.runner import SimulationRunner
    from aria_world.config import SimulationConfig

    start = time.time()
    config = SimulationConfig(initial_agents=10, max_days=kwargs.get("days", 50), seed=kwargs.get("seed", 42))
    runner = SimulationRunner(config)
    result = runner.run(days=kwargs.get("days", 50), seed=kwargs.get("seed", 42))
    duration_ms = (time.time() - start) * 1000

    survival_rate = result.get("survival_rate", 0.0)
    return BenchmarkResult(
        task_name="simulation_survival_rate",
        category="simulation",
        success=survival_rate > 0.3,
        score=survival_rate,
        confidence=0.9,
        duration_ms=duration_ms,
        details={"survival_rate": survival_rate, "final_population": result.get("final_population", 0)},
    )


def bench_simulation_happiness(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Measure average happiness across simulation."""
    from aria_world.runner import SimulationRunner
    from aria_world.config import SimulationConfig

    start = time.time()
    config = SimulationConfig(initial_agents=10, max_days=kwargs.get("days", 50), seed=kwargs.get("seed", 42))
    runner = SimulationRunner(config)
    result = runner.run(days=kwargs.get("days", 50), seed=kwargs.get("seed", 42))
    duration_ms = (time.time() - start) * 1000

    happiness = result.get("average_happiness", 0.0)
    return BenchmarkResult(
        task_name="simulation_happiness",
        category="simulation",
        success=happiness > 0.3,
        score=min(1.0, happiness),
        confidence=0.8,
        duration_ms=duration_ms,
        details={"average_happiness": happiness},
    )


def bench_simulation_food_security(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Measure food production vs consumption."""
    from aria_world.runner import SimulationRunner
    from aria_world.config import SimulationConfig

    start = time.time()
    config = SimulationConfig(initial_agents=10, max_days=kwargs.get("days", 50), seed=kwargs.get("seed", 42))
    runner = SimulationRunner(config)
    result = runner.run(days=kwargs.get("days", 50), seed=kwargs.get("seed", 42))
    duration_ms = (time.time() - start) * 1000

    survival = result.get("survival_rate", 0.0)
    score = min(1.0, survival * 1.2)
    return BenchmarkResult(
        task_name="simulation_food_security",
        category="simulation",
        success=survival > 0.4,
        score=score,
        confidence=0.8,
        duration_ms=duration_ms,
        details={"survival_rate": survival},
    )


def bench_simulation_social_cohesion(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Measure social cohesion via trust levels."""
    from aria_world.runner import SimulationRunner
    from aria_world.config import SimulationConfig

    start = time.time()
    config = SimulationConfig(initial_agents=10, max_days=kwargs.get("days", 50), seed=kwargs.get("seed", 42))
    runner = SimulationRunner(config)
    result = runner.run(days=kwargs.get("days", 50), seed=kwargs.get("seed", 42))
    duration_ms = (time.time() - start) * 1000

    conflicts = result.get("total_conflicts", 0)
    days = max(result.get("days_run", 1), 1)
    conflict_rate = conflicts / days
    score = max(0.0, 1.0 - conflict_rate)
    return BenchmarkResult(
        task_name="simulation_social_cohesion",
        category="simulation",
        success=conflict_rate < 0.5,
        score=score,
        confidence=0.7,
        duration_ms=duration_ms,
        details={"conflict_rate": conflict_rate, "total_conflicts": conflicts},
    )


def bench_simulation_economy(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Measure economic activity — trade volume and resource diversity."""
    from aria_world.runner import SimulationRunner
    from aria_world.config import SimulationConfig

    start = time.time()
    config = SimulationConfig(initial_agents=10, max_days=kwargs.get("days", 50), seed=kwargs.get("seed", 42))
    runner = SimulationRunner(config)
    result = runner.run(days=kwargs.get("days", 50), seed=kwargs.get("seed", 42))
    duration_ms = (time.time() - start) * 1000

    trades = result.get("total_trades", 0)
    days = max(result.get("days_run", 1), 1)
    trade_volume = trades / days
    score = min(1.0, trade_volume / 5.0)
    return BenchmarkResult(
        task_name="simulation_economy",
        category="simulation",
        success=trade_volume > 0,
        score=score,
        confidence=0.7,
        duration_ms=duration_ms,
        details={"trade_volume": trade_volume, "total_trades": trades},
    )


def bench_simulation_growth(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Measure village population growth."""
    from aria_world.runner import SimulationRunner
    from aria_world.config import SimulationConfig

    start = time.time()
    config = SimulationConfig(initial_agents=10, max_days=kwargs.get("days", 50), seed=kwargs.get("seed", 42))
    runner = SimulationRunner(config)
    result = runner.run(days=kwargs.get("days", 50), seed=kwargs.get("seed", 42))
    duration_ms = (time.time() - start) * 1000

    initial = result.get("initial_population", 10)
    final = result.get("final_population", 0)
    growth = final / max(initial, 1)
    score = min(1.0, growth / 2.0)
    return BenchmarkResult(
        task_name="simulation_growth",
        category="simulation",
        success=growth >= 1.0,
        score=score,
        confidence=0.9,
        duration_ms=duration_ms,
        details={"initial": initial, "final": final, "growth_ratio": growth},
    )


def bench_simulation_learning(aria: Any, **kwargs: Any) -> BenchmarkResult:
    """Measure knowledge growth per agent."""
    from aria_world.runner import SimulationRunner
    from aria_world.config import SimulationConfig

    start = time.time()
    config = SimulationConfig(initial_agents=10, max_days=kwargs.get("days", 50), seed=kwargs.get("seed", 42))
    runner = SimulationRunner(config)
    result = runner.run(days=kwargs.get("days", 50), seed=kwargs.get("seed", 42))
    duration_ms = (time.time() - start) * 1000

    avg_knowledge = result.get("average_knowledge", 0.0)
    score = min(1.0, avg_knowledge / 20.0)
    return BenchmarkResult(
        task_name="simulation_learning",
        category="simulation",
        success=avg_knowledge > 0,
        score=score,
        confidence=0.8,
        duration_ms=duration_ms,
        details={"average_knowledge": avg_knowledge},
    )


def register(registry: Any) -> None:
    """Register simulation benchmark tasks."""
    tasks = [
        ("simulation_survival_rate", "Evaluate agent survival rate", bench_simulation_survival_rate),
        ("simulation_happiness", "Evaluate average happiness", bench_simulation_happiness),
        ("simulation_food_security", "Evaluate food production vs consumption", bench_simulation_food_security),
        ("simulation_social_cohesion", "Evaluate social cohesion via trust", bench_simulation_social_cohesion),
        ("simulation_economy", "Evaluate economic activity", bench_simulation_economy),
        ("simulation_growth", "Evaluate village population growth", bench_simulation_growth),
        ("simulation_learning", "Evaluate knowledge growth per agent", bench_simulation_learning),
    ]
    for name, desc, func in tasks:
        registry.register_task(name, "simulation", desc, func)
    registry.register_suite("simulation", [t[0] for t in tasks])
