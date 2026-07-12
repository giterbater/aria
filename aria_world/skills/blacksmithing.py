"""Blacksmithing skill — produce tools from iron and wood."""

from __future__ import annotations

from typing import Any

from aria_core.skills.interfaces import SkillMeta, SkillResult


class BlacksmithingSkill:
    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="blacksmithing",
            description="Forge tools from iron and wood",
            category="village",
            tags=["tools", "crafting", "iron"],
            timeout_seconds=5.0,
        )

    def execute(self, **kwargs: Any) -> SkillResult:
        iron_available = kwargs.get("iron_available", 0)
        wood_available = kwargs.get("wood_available", 0)
        energy = kwargs.get("energy", 100)

        if iron_available < 2:
            return SkillResult.fail("Not enough iron (need 2)")
        if wood_available < 1:
            return SkillResult.fail("Not enough wood (need 1)")
        if energy < 10:
            return SkillResult.fail("Too exhausted to forge")

        return SkillResult.ok(
            output="Forged 1 tool",
            tools_produced=1,
            iron_used=2,
            wood_used=1,
            energy_cost=10,
        )

    def validate(self, **kwargs: Any) -> bool:
        return kwargs.get("iron_available", 0) >= 2 and kwargs.get("wood_available", 0) >= 1

    def rollback(self, context: dict) -> SkillResult:
        return SkillResult.ok(output="Nothing to rollback")
