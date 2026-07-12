"""Core data types for ARIA World simulation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ResourceType(str, Enum):
    WOOD = "wood"
    STONE = "stone"
    FOOD = "food"
    WATER = "water"
    IRON = "iron"
    TOOLS = "tools"


RESOURCE_VALUES: dict[ResourceType, float] = {
    ResourceType.WOOD: 1.0,
    ResourceType.STONE: 1.5,
    ResourceType.FOOD: 2.0,
    ResourceType.WATER: 1.0,
    ResourceType.IRON: 3.0,
    ResourceType.TOOLS: 5.0,
}


class Occupation(str, Enum):
    FARMER = "farmer"
    BUILDER = "builder"
    HUNTER = "hunter"
    MERCHANT = "merchant"
    BLACKSMITH = "blacksmith"


@dataclass
class ResourceInventory:
    resources: dict[ResourceType, float] = field(default_factory=dict)

    def has(self, resource: ResourceType, amount: float) -> bool:
        return self.resources.get(resource, 0.0) >= amount

    def add(self, resource: ResourceType, amount: float) -> None:
        self.resources[resource] = self.resources.get(resource, 0.0) + amount

    def remove(self, resource: ResourceType, amount: float) -> bool:
        current = self.resources.get(resource, 0.0)
        if current < amount:
            return False
        self.resources[resource] = current - amount
        return True

    def transfer(self, other: ResourceInventory, resource: ResourceType, amount: float) -> bool:
        if not self.remove(resource, amount):
            return False
        other.add(resource, amount)
        return True

    def total_value(self) -> float:
        return sum(qty * RESOURCE_VALUES.get(r, 1.0) for r, qty in self.resources.items())

    def to_dict(self) -> dict[str, float]:
        return {r.value: qty for r, qty in self.resources.items() if qty > 0}


@dataclass
class AgentNeeds:
    hunger: float = 50.0
    sleep: float = 50.0
    energy: float = 80.0
    safety: float = 70.0
    social: float = 50.0

    def most_urgent(self) -> tuple[str, float]:
        needs = {
            "hunger": self.hunger,
            "sleep": self.sleep,
            "energy": 100.0 - self.energy,
            "safety": 100.0 - self.safety,
            "social": self.social,
        }
        name = max(needs, key=needs.get)
        return name, needs[name]

    def overall_wellbeing(self) -> float:
        return (
            (100.0 - self.hunger)
            + (100.0 - self.sleep)
            + self.energy
            + self.safety
            + (100.0 - self.social)
        ) / 500.0

    def is_dangerous(self) -> bool:
        return self.hunger >= 100 or self.sleep >= 100

    def tick(self, occupation: str, social_interactions: int, rng: Any = None) -> None:
        import random as _random
        r = rng or _random.Random()
        self.hunger = min(100.0, self.hunger + 6.0 + r.uniform(0, 3))
        self.sleep = min(100.0, self.sleep + 8.0 + r.uniform(0, 2))
        energy_cost = {"farmer": 7, "builder": 10, "hunter": 12, "merchant": 4, "blacksmith": 9}
        self.energy = max(0.0, self.energy - energy_cost.get(occupation, 6) - r.uniform(0, 2))
        self.safety = min(100.0, self.safety + r.uniform(-2, 1))
        self.social = min(100.0, self.social + 2.0 - social_interactions * 3.0)


@dataclass
class Personality:
    aggression: float = 0.5
    generosity: float = 0.5
    diligence: float = 0.5
    curiosity: float = 0.5
    sociability: float = 0.5

    def to_cognitive_modifiers(self) -> dict[str, float]:
        return {
            "confidence": self.diligence * 0.2,
            "curiosity": self.curiosity * 0.3,
            "frustration": self.aggression * 0.1,
            "caution": (1.0 - self.aggression) * 0.2,
            "persistence": self.diligence * 0.2,
            "novelty": self.curiosity * 0.2,
        }


@dataclass
class Family:
    parent_a: str = ""
    parent_b: str = ""
    children: list[str] = field(default_factory=list)
    formed_day: int = 0


@dataclass
class AgentState:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Unknown"
    age: int = 25
    money: float = 10.0
    inventory: ResourceInventory = field(default_factory=ResourceInventory)
    needs: AgentNeeds = field(default_factory=AgentNeeds)
    occupation: Occupation = Occupation.FARMER
    personality: Personality = field(default_factory=Personality)
    alive: bool = True
    cause_of_death: str | None = None
    days_survived: int = 0
    total_actions: int = 0
    total_reflections: int = 0
    knowledge_entries: int = 0
    parent_ids: list[str] = field(default_factory=list)

    def happiness(self) -> float:
        need_score = self.needs.overall_wellbeing()
        money_score = min(1.0, self.money / 50.0)
        return (need_score * 0.6 + money_score * 0.2 + 0.2)


@dataclass
class WorldState:
    day: int = 0
    resources: dict[ResourceType, float] = field(default_factory=dict)
    buildings: dict[str, int] = field(default_factory=dict)
    families: list[Family] = field(default_factory=list)
    total_trades: int = 0
    total_conflicts: int = 0
    total_births: int = 0
    events_history: list[dict] = field(default_factory=list)
    population_history: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "resources": {r.value: q for r, q in self.resources.items()},
            "buildings": dict(self.buildings),
            "total_trades": self.total_trades,
            "total_conflicts": self.total_conflicts,
            "total_births": self.total_births,
            "population_history": self.population_history,
        }
