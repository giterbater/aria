"""Reproduction system — pairing, childbirth, child growth."""

from __future__ import annotations

import random as _random
import uuid
from typing import Any

from .models import AgentState, AgentNeeds, Personality, Occupation, ResourceInventory, ResourceType, Family
from .config import SimulationConfig


class ReproductionSystem:
    def __init__(self, config: SimulationConfig, rng: _random.Random | None = None) -> None:
        self._config = config
        self._rng = rng or _random.Random()

    def check_reproduction_opportunities(
        self,
        agents: list[AgentState],
        trust_fn: Any,
    ) -> list[tuple[str, str]]:
        eligible = [
            a for a in agents
            if a.alive
            and self._config.reproduction_age_min <= a.age <= self._config.reproduction_age_max
            and a.needs.social > 50
        ]
        pairs: list[tuple[str, str]] = []
        for i, a in enumerate(eligible):
            for b in eligible[i + 1:]:
                trust = trust_fn(a.id, b.id)
                if trust >= self._config.reproduction_trust_min:
                    if a.inventory.has(ResourceType.FOOD, self._config.child_care_food_cost):
                        if self._rng.random() < self._config.reproduction_chance:
                            pairs.append((a.id, b.id))
        return pairs

    def create_child(
        self,
        parent_a: AgentState,
        parent_b: AgentState,
        day: int,
    ) -> AgentState:
        pa = parent_a.personality
        pb = parent_b.personality
        child_personality = Personality(
            aggression=(pa.aggression + pb.aggression) / 2 + self._rng.uniform(-0.1, 0.1),
            generosity=(pa.generosity + pb.generosity) / 2 + self._rng.uniform(-0.1, 0.1),
            diligence=(pa.diligence + pb.diligence) / 2 + self._rng.uniform(-0.1, 0.1),
            curiosity=(pa.curiosity + pb.curiosity) / 2 + self._rng.uniform(-0.1, 0.1),
            sociability=(pa.sociability + pb.sociability) / 2 + self._rng.uniform(-0.1, 0.1),
        )
        child_personality.aggression = max(0.0, min(1.0, child_personality.aggression))
        child_personality.generosity = max(0.0, min(1.0, child_personality.generosity))
        child_personality.diligence = max(0.0, min(1.0, child_personality.diligence))
        child_personality.curiosity = max(0.0, min(1.0, child_personality.curiosity))
        child_personality.sociability = max(0.0, min(1.0, child_personality.sociability))

        occupation = self._rng.choice([parent_a.occupation, parent_b.occupation])

        child = AgentState(
            id=str(uuid.uuid4())[:8],
            name=f"Child_{str(uuid.uuid4())[:4]}",
            age=0,
            money=0.0,
            inventory=ResourceInventory(),
            needs=AgentNeeds(hunger=30, sleep=30, energy=90, safety=80, social=40),
            occupation=occupation,
            personality=child_personality,
            parent_ids=[parent_a.id, parent_b.id],
        )

        parent_a.inventory.remove(ResourceType.FOOD, self._config.child_care_food_cost)
        parent_a.inventory.remove(ResourceType.WATER, self._config.child_care_water_cost)
        parent_b.inventory.remove(ResourceType.FOOD, self._config.child_care_food_cost)
        parent_b.inventory.remove(ResourceType.WATER, self._config.child_care_water_cost)

        return child

    def tick_child(self, agent: AgentState) -> None:
        if agent.age < 5:
            agent.needs.hunger = min(100, agent.needs.hunger + 10)
            agent.needs.energy = max(0, agent.needs.energy - 5)
        elif agent.age < 12:
            agent.needs.hunger = min(100, agent.needs.hunger + 7)
            agent.needs.energy = max(0, agent.needs.energy - 3)
