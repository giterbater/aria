"""SimulationRunner — orchestrates full simulation runs and benchmark integration."""

from __future__ import annotations

import datetime
import json
import logging
import uuid
from typing import Any

from .config import SimulationConfig
from .world import WorldEngine
from .metrics import SimulationMetrics

logger = logging.getLogger("aria_world.runner")


class SimulationRunner:
    def __init__(self, config: SimulationConfig | None = None) -> None:
        self.config = config or SimulationConfig()

    def run(self, days: int | None = None, seed: int | None = None) -> dict:
        config = SimulationConfig(
            initial_agents=self.config.initial_agents,
            max_agents=self.config.max_agents,
            max_days=days or self.config.max_days,
            starting_age_range=self.config.starting_age_range,
            max_age=self.config.max_age,
            initial_resources=dict(self.config.initial_resources),
            resource_regen_rates=dict(self.config.resource_regen_rates),
            event_probability=self.config.event_probability,
            reproduction_age_min=self.config.reproduction_age_min,
            reproduction_age_max=self.config.reproduction_age_max,
            reproduction_trust_min=self.config.reproduction_trust_min,
            reproduction_chance=self.config.reproduction_chance,
            seed=seed if seed is not None else self.config.seed,
            verbose=self.config.verbose,
            _disable_reflection=self.config._disable_reflection,
            _disable_memory=self.config._disable_memory,
            _disable_trust=self.config._disable_trust,
            _disable_curiosity=self.config._disable_curiosity,
        )

        world = WorldEngine(config)
        world.initialize()
        result = world.run(days)
        world.shutdown()
        return result

    def run_comparison(self, days: int = 100, runs: int = 3, base_seed: int = 42) -> dict:
        results = []
        for i in range(runs):
            result = self.run(days=days, seed=base_seed + i)
            results.append(result)

        avg_survival = sum(r["survival_rate"] for r in results) / len(results)
        avg_happiness = sum(r["average_happiness"] for r in results) / len(results)
        avg_knowledge = sum(r["average_knowledge"] for r in results) / len(results)

        return {
            "runs": runs,
            "days": days,
            "average_survival_rate": avg_survival,
            "average_happiness": avg_happiness,
            "average_knowledge": avg_knowledge,
            "individual_results": [
                {"seed": r["seed"], "survival": r["survival_rate"], "happiness": r["average_happiness"]}
                for r in results
            ],
        }

    def benchmark(self, days: int = 50, seed: int = 42) -> dict:
        from benchmarks.benchmark_result import BenchmarkResult, BenchmarkRun

        result = self.run(days=days, seed=seed)
        metrics = SimulationMetrics.from_simulation_result(result)

        benchmark_results = [
            BenchmarkResult(
                task_name="simulation_survival_rate",
                category="simulation",
                success=metrics.survival_rate > 0.3,
                score=metrics.survival_rate,
                confidence=0.9,
                details={"survival_rate": metrics.survival_rate},
            ),
            BenchmarkResult(
                task_name="simulation_happiness",
                category="simulation",
                success=metrics.average_happiness > 0.3,
                score=metrics.average_happiness,
                confidence=0.8,
                details={"average_happiness": metrics.average_happiness},
            ),
            BenchmarkResult(
                task_name="simulation_knowledge",
                category="simulation",
                success=metrics.average_knowledge > 0,
                score=min(1.0, metrics.average_knowledge / 20.0),
                confidence=0.8,
                details={"average_knowledge": metrics.average_knowledge},
            ),
            BenchmarkResult(
                task_name="simulation_economy",
                category="simulation",
                success=metrics.trade_volume > 0,
                score=min(1.0, metrics.trade_volume / 5.0),
                confidence=0.7,
                details={"trade_volume": metrics.trade_volume, "conflict_rate": metrics.conflict_rate},
            ),
            BenchmarkResult(
                task_name="simulation_growth",
                category="simulation",
                success=metrics.village_growth >= 1.0,
                score=min(1.0, metrics.village_growth / 2.0),
                confidence=0.9,
                details={"village_growth": metrics.village_growth, "births": metrics.total_births},
            ),
        ]

        metric_set = metrics.to_metric_set(
            run_id=f"sim_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.datetime.now().isoformat(),
        )

        return {
            "simulation_result": result,
            "metrics": metrics,
            "benchmark_results": benchmark_results,
            "metric_set": metric_set,
        }

    def export_results(self, result: dict, path: str) -> None:
        serializable = {
            k: v for k, v in result.items()
            if k != "daily_results"
        }
        serializable["daily_results_count"] = len(result.get("daily_results", []))
        with open(path, "w") as f:
            json.dump(serializable, f, indent=2, default=str)
