"""Resource management — inventory, scarcity, regeneration."""

from __future__ import annotations

import random as _random
from typing import Any

from .models import ResourceType, ResourceInventory, Occupation, AgentState
from .config import SimulationConfig


class ResourceSystem:
    def __init__(self, config: SimulationConfig, rng: _random.Random | None = None) -> None:
        self._config = config
        self._rng = rng or _random.Random()

    def initialize_world_resources(self) -> dict[ResourceType, float]:
        return {ResourceType(k): v for k, v in self._config.initial_resources.items()}

    def initialize_agent_inventory(self, occupation: Occupation) -> ResourceInventory:
        inv = ResourceInventory()
        starter = {
            Occupation.FARMER: {ResourceType.FOOD: 5, ResourceType.WATER: 5, ResourceType.WOOD: 2},
            Occupation.BUILDER: {ResourceType.WOOD: 8, ResourceType.STONE: 5, ResourceType.FOOD: 3},
            Occupation.HUNTER: {ResourceType.FOOD: 4, ResourceType.WATER: 3, ResourceType.WOOD: 3},
            Occupation.MERCHANT: {ResourceType.FOOD: 3, ResourceType.WATER: 3},
            Occupation.BLACKSMITH: {ResourceType.IRON: 4, ResourceType.WOOD: 4, ResourceType.FOOD: 3},
        }
        for res, qty in starter.get(occupation, {}).items():
            inv.add(res, qty)
        return inv

    def regen_world_resources(self, world_resources: dict[ResourceType, float]) -> None:
        for res, rate in self._config.resource_regen_rates.items():
            rt = ResourceType(res)
            current = world_resources.get(rt, 0)
            bonus = self._rng.uniform(0, rate * 0.3)
            world_resources[rt] = current + rate + bonus

    def consume_needs(self, agent: AgentState) -> None:
        inv = agent.inventory
        if agent.needs.hunger > 60 and inv.has(ResourceType.FOOD, 1):
            inv.remove(ResourceType.FOOD, 1)
            agent.needs.hunger = max(0, agent.needs.hunger - 25)
        if agent.needs.sleep > 70 and inv.has(ResourceType.WATER, 0.5):
            inv.remove(ResourceType.WATER, 0.5)
            agent.needs.sleep = max(0, agent.needs.sleep - 15)

    def check_scarcity(self, world_resources: dict[ResourceType, float]) -> list[str]:
        warnings = []
        for rt in ResourceType:
            if world_resources.get(rt, 0) < 20:
                warnings.append(f"{rt.value} is scarce ({world_resources.get(rt, 0):.0f} remaining)")
        return warnings

    def can_produce(self, occupation: Occupation, world_resources: dict[ResourceType, float]) -> bool:
        costs = {
            Occupation.FARMER: {ResourceType.WATER: 1},
            Occupation.BUILDER: {ResourceType.WOOD: 3, ResourceType.STONE: 2},
            Occupation.HUNTER: {},
            Occupation.MERCHANT: {},
            Occupation.BLACKSMITH: {ResourceType.IRON: 2, ResourceType.WOOD: 1},
        }
        for res, qty in costs.get(occupation, {}).items():
            if world_resources.get(res, 0) < qty:
                return False
        return True

    def produce(self, occupation: Occupation, world_resources: dict[ResourceType, float]) -> dict[ResourceType, float]:
        produced: dict[ResourceType, float] = {}
        if not self.can_produce(occupation, world_resources):
            return produced

        costs = {
            Occupation.FARMER: {ResourceType.WATER: 1},
            Occupation.BUILDER: {ResourceType.WOOD: 3, ResourceType.STONE: 2},
            Occupation.BLACKSMITH: {ResourceType.IRON: 2, ResourceType.WOOD: 1},
        }
        for res, qty in costs.get(occupation, {}).items():
            world_resources[res] = world_resources.get(res, 0) - qty

        if occupation == Occupation.FARMER:
            qty = self._rng.randint(2, 4)
            produced[ResourceType.FOOD] = qty
        elif occupation == Occupation.BUILDER:
            produced[ResourceType.TOOLS] = 1
        elif occupation == Occupation.HUNTER:
            qty = self._rng.randint(2, 5)
            produced[ResourceType.FOOD] = qty
        elif occupation == Occupation.BLACKSMITH:
            produced[ResourceType.TOOLS] = 1
        return produced
