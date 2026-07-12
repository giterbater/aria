"""Occupation system — what agents produce and consume."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from .models import ResourceType, Occupation


@runtime_checkable
class OccupationHandler(Protocol):
    @property
    def name(self) -> Occupation: ...
    def can_produce(self, world_resources: dict[ResourceType, float]) -> bool: ...
    def produce(self, world_resources: dict[ResourceType, float], diligence: float, rng: object) -> dict[ResourceType, float]: ...
    def daily_food_cost(self) -> float: ...
    def daily_water_cost(self) -> float: ...
    def daily_energy_cost(self) -> float: ...
    def skill_name(self) -> str: ...


@dataclass
class FarmerHandler:
    @property
    def name(self) -> Occupation:
        return Occupation.FARMER

    def can_produce(self, world_resources: dict[ResourceType, float]) -> bool:
        return world_resources.get(ResourceType.WATER, 0) >= 1

    def produce(self, world_resources: dict[ResourceType, float], diligence: float, rng: object) -> dict[ResourceType, float]:
        import random as _random
        r = rng if isinstance(rng, _random.Random) else _random.Random()
        world_resources[ResourceType.WATER] = world_resources.get(ResourceType.WATER, 0) - 1
        base = r.randint(2, 4)
        bonus = int(diligence * 2)
        return {ResourceType.FOOD: base + bonus}

    def daily_food_cost(self) -> float:
        return 1.0

    def daily_water_cost(self) -> float:
        return 1.0

    def daily_energy_cost(self) -> float:
        return 7.0

    def skill_name(self) -> str:
        return "farming"


@dataclass
class BuilderHandler:
    @property
    def name(self) -> Occupation:
        return Occupation.BUILDER

    def can_produce(self, world_resources: dict[ResourceType, float]) -> bool:
        return (world_resources.get(ResourceType.WOOD, 0) >= 3
                and world_resources.get(ResourceType.STONE, 0) >= 2)

    def produce(self, world_resources: dict[ResourceType, float], diligence: float, rng: object) -> dict[ResourceType, float]:
        world_resources[ResourceType.WOOD] = world_resources.get(ResourceType.WOOD, 0) - 3
        world_resources[ResourceType.STONE] = world_resources.get(ResourceType.STONE, 0) - 2
        return {ResourceType.TOOLS: 1}

    def daily_food_cost(self) -> float:
        return 1.0

    def daily_water_cost(self) -> float:
        return 0.5

    def daily_energy_cost(self) -> float:
        return 10.0

    def skill_name(self) -> str:
        return "building"


@dataclass
class HunterHandler:
    @property
    def name(self) -> Occupation:
        return Occupation.HUNTER

    def can_produce(self, world_resources: dict[ResourceType, float]) -> bool:
        return True

    def produce(self, world_resources: dict[ResourceType, float], diligence: float, rng: object) -> dict[ResourceType, float]:
        import random as _random
        r = rng if isinstance(rng, _random.Random) else _random.Random()
        base = r.randint(2, 5)
        bonus = int(diligence * 2)
        return {ResourceType.FOOD: base + bonus}

    def daily_food_cost(self) -> float:
        return 1.5

    def daily_water_cost(self) -> float:
        return 0.5

    def daily_energy_cost(self) -> float:
        return 12.0

    def skill_name(self) -> str:
        return "hunting"


@dataclass
class MerchantHandler:
    @property
    def name(self) -> Occupation:
        return Occupation.MERCHANT

    def can_produce(self, world_resources: dict[ResourceType, float]) -> bool:
        return True

    def produce(self, world_resources: dict[ResourceType, float], diligence: float, rng: object) -> dict[ResourceType, float]:
        import random as _random
        r = rng if isinstance(rng, _random.Random) else _random.Random()
        return {ResourceType.FOOD: r.randint(1, 2)} if r.random() < 0.3 else {}

    def daily_food_cost(self) -> float:
        return 1.0

    def daily_water_cost(self) -> float:
        return 0.5

    def daily_energy_cost(self) -> float:
        return 4.0

    def skill_name(self) -> str:
        return "trading"


@dataclass
class BlacksmithHandler:
    @property
    def name(self) -> Occupation:
        return Occupation.BLACKSMITH

    def can_produce(self, world_resources: dict[ResourceType, float]) -> bool:
        return (world_resources.get(ResourceType.IRON, 0) >= 2
                and world_resources.get(ResourceType.WOOD, 0) >= 1)

    def produce(self, world_resources: dict[ResourceType, float], diligence: float, rng: object) -> dict[ResourceType, float]:
        world_resources[ResourceType.IRON] = world_resources.get(ResourceType.IRON, 0) - 2
        world_resources[ResourceType.WOOD] = world_resources.get(ResourceType.WOOD, 0) - 1
        return {ResourceType.TOOLS: 1}

    def daily_food_cost(self) -> float:
        return 1.0

    def daily_water_cost(self) -> float:
        return 1.0

    def daily_energy_cost(self) -> float:
        return 9.0

    def skill_name(self) -> str:
        return "blacksmithing"


OCCUPATIONS: dict[Occupation, OccupationHandler] = {
    Occupation.FARMER: FarmerHandler(),
    Occupation.BUILDER: BuilderHandler(),
    Occupation.HUNTER: HunterHandler(),
    Occupation.MERCHANT: MerchantHandler(),
    Occupation.BLACKSMITH: BlacksmithHandler(),
}
