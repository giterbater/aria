"""Farming skill — produce food from water."""

from __future__ import annotations

import random as _random
from typing import Any

from aria_core.skills.interfaces import SkillMeta, SkillResult


class FarmingSkill:
    def __init__(self) -> None:
        self._rng = _random.Random()

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="farming",
            description="Produce food from water using farming techniques",
            category="village",
            tags=["food", "farming", "production"],
            timeout_seconds=5.0,
        )

    def execute(self, **kwargs: Any) -> SkillResult:
        water_available = kwargs.get("water_available", 0)
        energy = kwargs.get("energy", 100)
        diligence = kwargs.get("diligence", 0.5)

        if water_available < 1:
            return SkillResult.fail("Not enough water to farm")
        if energy < 5:
            return SkillResult.fail("Too exhausted to farm")

        base_yield = self._rng.randint(2, 4)
        bonus = int(diligence * 2)
        food_produced = base_yield + bonus

        return SkillResult.ok(
            output=f"Produced {food_produced} food",
            food_produced=food_produced,
            water_used=1,
            energy_cost=5,
        )

    def validate(self, **kwargs: Any) -> bool:
        return kwargs.get("water_available", 0) >= 1

    def rollback(self, context: dict) -> SkillResult:
        return SkillResult.ok(output="Nothing to rollback")
