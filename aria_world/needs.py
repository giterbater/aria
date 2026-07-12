"""Needs system — maps simulation vital needs to ARIA cognitive needs."""

from __future__ import annotations

import random as _random
from typing import Any

from .models import AgentNeeds, AgentState, Occupation
from .config import SimulationConfig


class NeedsSystem:
    def __init__(self, config: SimulationConfig, rng: _random.Random | None = None) -> None:
        self._config = config
        self._rng = rng or _random.Random()

    def assess_needs(self, agent: AgentState) -> list[dict]:
        needs = agent.needs
        urgent = []
        if needs.hunger > 50:
            urgent.append({"need": "hunger", "severity": needs.hunger / 100.0, "suggested_action": "eat"})
        if needs.sleep > 60:
            urgent.append({"need": "sleep", "severity": needs.sleep / 100.0, "suggested_action": "rest"})
        if needs.energy < 30:
            urgent.append({"need": "energy", "severity": (100 - needs.energy) / 100.0, "suggested_action": "recover"})
        if needs.safety < 40:
            urgent.append({"need": "safety", "severity": (100 - needs.safety) / 100.0, "suggested_action": "secure_area"})
        if needs.social > 60:
            urgent.append({"need": "social", "severity": needs.social / 100.0, "suggested_action": "socialize"})
        urgent.sort(key=lambda x: x["severity"], reverse=True)
        if not urgent:
            urgent.append({"need": "work", "severity": 0.5, "suggested_action": agent.occupation.value})
        return urgent

    def derive_cognitive_needs(self, agent_needs: AgentNeeds) -> dict[str, float]:
        modifiers: dict[str, float] = {}
        if agent_needs.hunger > 70:
            modifiers["frustration"] = 0.2
            modifiers["caution"] = 0.1
        if agent_needs.sleep > 80:
            modifiers["confidence"] = -0.15
            modifiers["persistence"] = -0.1
        if agent_needs.safety < 30:
            modifiers["caution"] = 0.3
            modifiers["curiosity"] = -0.2
        if agent_needs.social > 70:
            modifiers["novelty"] = 0.1
        if agent_needs.energy < 20:
            modifiers["persistence"] = -0.15
        return modifiers

    def check_survival(self, agent: AgentState) -> bool:
        if agent.needs.hunger >= 100:
            agent.alive = False
            agent.cause_of_death = "starvation"
            return False
        if agent.needs.sleep >= 100:
            agent.needs.sleep = 95
            agent.needs.energy = max(0, agent.needs.energy - 20)
        if agent.age > self._config.max_age:
            agent.alive = False
            agent.cause_of_death = "old_age"
            return False
        return True

    def tick_needs(self, agent: AgentState) -> None:
        agent.needs.tick(agent.occupation.value, 0, self._rng)
