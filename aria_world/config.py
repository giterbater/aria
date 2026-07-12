"""Tunable simulation parameters."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SimulationConfig:
    initial_agents: int = 10
    max_agents: int = 20
    max_days: int = 100
    starting_age_range: tuple[int, int] = (20, 40)
    max_age: int = 80

    initial_resources: dict[str, float] = field(default_factory=lambda: {
        "wood": 500, "stone": 300, "food": 200, "water": 400, "iron": 100,
    })
    resource_regen_rates: dict[str, float] = field(default_factory=lambda: {
        "wood": 20, "stone": 10, "food": 15, "water": 30, "iron": 5,
    })

    hunger_rate: float = 8.0
    sleep_rate: float = 10.0
    energy_decay: float = 5.0
    social_decay: float = 3.0

    trade_tax: float = 0.1
    starting_money_range: tuple[float, float] = (5.0, 20.0)

    event_probability: float = 0.15
    conflict_threshold: float = 0.3

    reproduction_age_min: int = 18
    reproduction_age_max: int = 50
    reproduction_trust_min: float = 60.0
    reproduction_chance: float = 0.10
    child_care_food_cost: float = 5.0
    child_care_water_cost: float = 5.0

    seed: int | None = None
    verbose: bool = False

    # Ablation flags
    _disable_reflection: bool = False
    _disable_memory: bool = False
    _disable_trust: bool = False
    _disable_curiosity: bool = False
