"""Simulation metrics — converts results to BenchmarkRunner-compatible MetricSet."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from benchmarks.metrics import MetricSet, MetricType


@dataclass
class SimulationMetrics:
    seed: int = 0
    days_run: int = 0
    initial_population: int = 0
    final_population: int = 0
    survival_rate: float = 0.0
    average_happiness: float = 0.0
    average_lifespan_days: float = 0.0
    average_knowledge: float = 0.0
    total_trades: int = 0
    total_conflicts: int = 0
    total_births: int = 0
    food_production_rate: float = 0.0
    conflict_rate: float = 0.0
    trade_volume: float = 0.0
    birth_rate: float = 0.0
    social_cohesion: float = 0.0
    goal_completion_rate: float = 0.0
    learning_speed: float = 0.0
    village_growth: float = 0.0

    @classmethod
    def from_simulation_result(cls, result: dict) -> SimulationMetrics:
        days = max(result.get("days_run", 1), 1)
        initial = result.get("initial_population", 10)
        final = result.get("final_population", 0)
        return cls(
            seed=result.get("seed", 0),
            days_run=days,
            initial_population=initial,
            final_population=final,
            survival_rate=result.get("survival_rate", 0.0),
            average_happiness=result.get("average_happiness", 0.0),
            average_lifespan_days=result.get("average_lifespan_days", 0.0),
            average_knowledge=result.get("average_knowledge", 0.0),
            total_trades=result.get("total_trades", 0),
            total_conflicts=result.get("total_conflicts", 0),
            total_births=result.get("total_births", 0),
            food_production_rate=result.get("total_trades", 0) / days,
            conflict_rate=result.get("total_conflicts", 0) / days,
            trade_volume=result.get("total_trades", 0) / days,
            birth_rate=result.get("total_births", 0) / days,
            social_cohesion=0.5,
            goal_completion_rate=result.get("survival_rate", 0.5),
            learning_speed=min(1.0, result.get("average_knowledge", 0) / 20.0),
            village_growth=final / max(initial, 1),
        )

    def to_metric_set(self, run_id: str = "", timestamp: str = "") -> MetricSet:
        ms = MetricSet(run_id=run_id, timestamp=timestamp)
        ms.add("simulation_survival_rate", self.survival_rate, MetricType.SIMULATION)
        ms.add("simulation_happiness", self.average_happiness, MetricType.SIMULATION)
        ms.add("simulation_lifespan", min(1.0, self.average_lifespan_days / 100.0), MetricType.SIMULATION)
        ms.add("simulation_knowledge", min(1.0, self.average_knowledge / 20.0), MetricType.SIMULATION)
        ms.add("simulation_conflict_rate", max(0.0, 1.0 - self.conflict_rate), MetricType.SIMULATION)
        ms.add("simulation_trade_volume", min(1.0, self.trade_volume / 5.0), MetricType.SIMULATION)
        ms.add("simulation_birth_rate", min(1.0, self.birth_rate), MetricType.SIMULATION)
        ms.add("simulation_village_growth", min(1.0, self.village_growth / 2.0), MetricType.SIMULATION)
        ms.add("simulation_learning_speed", self.learning_speed, MetricType.SIMULATION)
        ms.add("simulation_goal_completion", self.goal_completion_rate, MetricType.SIMULATION)
        return ms
