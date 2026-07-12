"""Building skill — produce structures from wood and stone."""

from __future__ import annotations

from typing import Any

from aria_core.skills.interfaces import SkillMeta, SkillResult


class BuildingSkill:
    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="building",
            description="Build structures from wood and stone",
            category="village",
            tags=["building", "construction", "tools"],
            timeout_seconds=5.0,
        )

    def execute(self, **kwargs: Any) -> SkillResult:
        wood_available = kwargs.get("wood_available", 0)
        stone_available = kwargs.get("stone_available", 0)
        energy = kwargs.get("energy", 100)

        if wood_available < 3:
            return SkillResult.fail("Not enough wood (need 3)")
        if stone_available < 2:
            return SkillResult.fail("Not enough stone (need 2)")
        if energy < 10:
            return SkillResult.fail("Too exhausted to build")

        return SkillResult.ok(
            output="Built a structure, produced 1 tool",
            tools_produced=1,
            wood_used=3,
            stone_used=2,
            energy_cost=10,
        )

    def validate(self, **kwargs: Any) -> bool:
        return kwargs.get("wood_available", 0) >= 3 and kwargs.get("stone_available", 0) >= 2

    def rollback(self, context: dict) -> SkillResult:
        return SkillResult.ok(output="Nothing to rollback")
