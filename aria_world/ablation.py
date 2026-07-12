"""Ablation study framework for ARIA World.

Runs controlled experiments by toggling cognitive components
and measuring impact on survival, knowledge, innovation, and learning.
"""

from __future__ import annotations

import random as _random
import statistics
from dataclasses import dataclass, field
from typing import Any

from .config import SimulationConfig
from .world import WorldEngine
from .runner import SimulationRunner


@dataclass
class AblationResult:
    name: str
    enabled: bool
    runs: list[dict] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.runs)

    def mean(self, key: str) -> float:
        values = [r.get(key, 0) for r in self.runs]
        return statistics.mean(values) if values else 0.0

    def stdev(self, key: str) -> float:
        values = [r.get(key, 0) for r in self.runs]
        return statistics.stdev(values) if len(values) > 1 else 0.0

    def ci95(self, key: str) -> tuple[float, float]:
        m = self.mean(key)
        s = self.stdev(key)
        n = self.n
        if n < 2:
            return (m, m)
        se = s / (n ** 0.5)
        return (m - 1.96 * se, m + 1.96 * se)


class AblationStudy:
    """Runs controlled ablation experiments."""

    def __init__(self, days: int = 200, agents: int = 10, runs_per_condition: int = 5) -> None:
        self.days = days
        self.agents = agents
        self.runs_per_condition = runs_per_condition

    def run_experiment(self, name: str, modify_fn: Any, seeds: list[int] | None = None) -> AblationResult:
        if seeds is None:
            seeds = list(range(1, self.runs_per_condition + 1))

        result = AblationResult(name=name, enabled=True)
        for seed in seeds:
            config = SimulationConfig(
                seed=seed,
                initial_agents=self.agents,
                max_days=self.days,
            )
            modify_fn(config)
            runner = SimulationRunner(config)
            run_result = runner.run(days=self.days, seed=seed)
            result.runs.append(run_result)
        return result

    def run_reflection_ablation(self, seeds: list[int] | None = None) -> tuple[AblationResult, AblationResult]:
        """Test: Does reflection improve survival and learning?"""
        def with_reflection(config):
            pass

        def without_reflection(config):
            config._disable_reflection = True

        on = self.run_experiment("reflection_on", with_reflection, seeds)
        off = self.run_experiment("reflection_off", without_reflection, seeds)
        return on, off

    def run_memory_ablation(self, seeds: list[int] | None = None) -> tuple[AblationResult, AblationResult]:
        """Test: Does memory improve planning and innovation?"""
        def with_memory(config):
            pass

        def without_memory(config):
            config._disable_memory = True

        on = self.run_experiment("memory_on", with_memory, seeds)
        off = self.run_experiment("memory_off", without_memory, seeds)
        return on, off

    def run_trust_ablation(self, seeds: list[int] | None = None) -> tuple[AblationResult, AblationResult]:
        """Test: Does trust-based teaching work?"""
        def with_trust(config):
            pass

        def without_trust(config):
            config._disable_trust = True

        on = self.run_experiment("trust_on", with_trust, seeds)
        off = self.run_experiment("trust_off", without_trust, seeds)
        return on, off

    def run_curiosity_ablation(self, seeds: list[int] | None = None) -> tuple[AblationResult, AblationResult]:
        """Test: Does curiosity drive innovation?"""
        def with_curiosity(config):
            pass

        def without_curiosity(config):
            config._disable_curiosity = True

        on = self.run_experiment("curiosity_on", with_curiosity, seeds)
        off = self.run_experiment("curiosity_off", without_curiosity, seeds)
        return on, off

    def run_all_ablations(self, seeds: list[int] | None = None) -> dict[str, tuple[AblationResult, AblationResult]]:
        """Run all ablation experiments."""
        if seeds is None:
            seeds = list(range(1, self.runs_per_condition + 1))

        return {
            "reflection": self.run_reflection_ablation(seeds),
            "memory": self.run_memory_ablation(seeds),
            "trust": self.run_trust_ablation(seeds),
            "curiosity": self.run_curiosity_ablation(seeds),
        }
