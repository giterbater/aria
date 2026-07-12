"""Hunting skill — produce food using energy and skill."""

from __future__ import annotations

import random as _random
from typing import Any

from aria_core.skills.interfaces import SkillMeta, SkillResult


class HuntingSkill:
    def __init__(self) -> None:
        self._rng = _random.Random()

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="hunting",
            description="Hunt for food in the wilderness",
            category="village",
            tags=["food", "hunting", "survival"],
            timeout_seconds=5.0,
        )

    def execute(self, **kwargs: Any) -> SkillResult:
        energy = kwargs.get("energy", 100)
        diligence = kwargs.get("diligence", 0.5)

        if energy < 15:
            return SkillResult.fail("Not enough energy to hunt (need 15)")

        base_yield = self._rng.randint(2, 5)
        bonus = int(diligence * 2)
        food_produced = base_yield + bonus

        return SkillResult.ok(
            output=f"Hunted successfully, produced {food_produced} food",
            food_produced=food_produced,
            energy_cost=15,
        )

    def validate(self, **kwargs: Any) -> bool:
        return kwargs.get("energy", 100) >= 15

    def rollback(self, context: dict) -> SkillResult:
        return SkillResult.ok(output="Nothing to rollback")
