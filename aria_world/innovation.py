"""Innovation system — recipe discovery and cumulative progress.

Agents discover new combinations of resources.
Knowledge graph grows with each discovery.
Every future agent benefits from past innovations.
"""

from __future__ import annotations

import random as _random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Recipe:
    name: str
    inputs: dict[str, float]      # resource → amount needed
    outputs: dict[str, float]     # resource → amount produced
    discovered_by: str            # agent_id
    day_discovered: int
    times_used: int = 0
    quality_bonus: float = 0.0    # extra output from expertise

    @property
    def efficiency(self) -> float:
        input_value = sum(self.inputs.values())
        output_value = sum(self.outputs.values())
        return output_value / max(input_value, 0.1)


@dataclass
class Innovation:
    name: str
    description: str
    discovered_by: str
    day_discovered: int
    recipes_unlocked: list[str] = field(default_factory=list)
    impact_score: float = 0.0     # measured impact on village survival


RECIPE_TEMPLATES = [
    {
        "name": "basic_food",
        "inputs": {"water": 1},
        "outputs": {"food": 3},
        "description": "Basic food production from water",
    },
    {
        "name": "tool_from_iron",
        "inputs": {"iron": 2, "wood": 1},
        "outputs": {"tools": 1},
        "description": "Forge tools from iron and wood",
    },
    {
        "name": "stone_tools",
        "inputs": {"stone": 3},
        "outputs": {"tools": 1},
        "description": "Crude tools from shaped stone",
    },
    {
        "name": "advanced_farming",
        "inputs": {"water": 1, "tools": 0.5},
        "outputs": {"food": 5},
        "description": "Efficient farming with better tools",
    },
    {
        "name": "trade_goods",
        "inputs": {"wood": 2, "stone": 1},
        "outputs": {"food": 2, "iron": 1},
        "description": "Exchange raw materials for diverse goods",
    },
    {
        "name": "iron_tools",
        "inputs": {"iron": 3, "wood": 2},
        "outputs": {"tools": 2},
        "description": "Improved tool production",
    },
    {
        "name": "water_purification",
        "inputs": {"wood": 1, "stone": 1},
        "outputs": {"water": 5},
        "description": "Filter and purify water using natural materials",
    },
    {
        "name": "storage_preservation",
        "inputs": {"wood": 3, "stone": 2},
        "outputs": {"food": 8},
        "description": "Build storage to preserve food longer",
    },
]


class InnovationSystem:
    """Manages recipe discovery and cumulative innovation."""

    def __init__(self, rng: _random.Random | None = None) -> None:
        self._rng = rng or _random.Random()
        self._recipes: dict[str, Recipe] = {}
        self._innovations: list[Innovation] = []
        self._available_templates = list(RECIPE_TEMPLATES)
        self._discovered_recipes: set[str] = set()

        for t in RECIPE_TEMPLATES[:3]:  # Start with 3 basic recipes
            self._unlock_recipe(t)

    def _unlock_recipe(self, template: dict) -> Recipe:
        recipe = Recipe(
            name=template["name"],
            inputs=template["inputs"],
            outputs=template["outputs"],
            discovered_by="initial",
            day_discovered=0,
        )
        self._recipes[recipe.name] = recipe
        self._discovered_recipes.add(recipe.name)
        return recipe

    def attempt_discovery(
        self,
        agent_id: str,
        skill_level: float,
        day: int,
        available_resources: dict[str, float],
    ) -> Recipe | None:
        """Attempt to discover a new recipe.

        Discovery depends on:
        - Skill level (higher = more likely)
        - Curiosity (personality trait)
        - Available resources (need materials to experiment)
        - Random luck
        """
        undiscovered = [
            t for t in self._available_templates
            if t["name"] not in self._discovered_recipes
        ]
        if not undiscovered:
            return None

        chance = 0.02 + skill_level * 0.08
        if self._rng.random() > chance:
            return None

        can_make = []
        for t in undiscovered:
            if all(available_resources.get(r, 0) >= a for r, a in t["inputs"].items()):
                can_make.append(t)

        if not can_make:
            template = self._rng.choice(undiscovered)
        else:
            template = self._rng.choice(can_make)

        recipe = Recipe(
            name=template["name"],
            inputs=template["inputs"],
            outputs=template["outputs"],
            discovered_by=agent_id,
            day_discovered=day,
        )
        self._recipes[recipe.name] = recipe
        self._discovered_recipes.add(template["name"])

        innovation = Innovation(
            name=f"discovery_{template['name']}",
            description=template["description"],
            discovered_by=agent_id,
            day_discovered=day,
            recipes_unlocked=[recipe.name],
        )
        self._innovations.append(innovation)

        return recipe

    def get_recipe(self, name: str) -> Recipe | None:
        return self._recipes.get(name)

    def get_all_recipes(self) -> list[Recipe]:
        return list(self._recipes.values())

    def get_best_recipe_for_output(self, output_resource: str) -> Recipe | None:
        candidates = [
            r for r in self._recipes.values()
            if output_resource in r.outputs
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda r: r.efficiency)

    def execute_recipe(
        self,
        recipe_name: str,
        available_resources: dict[str, float],
        quality_bonus: float = 0.0,
    ) -> dict[str, float] | None:
        """Execute a recipe if resources are available."""
        recipe = self._recipes.get(recipe_name)
        if not recipe:
            return None

        for res, amount in recipe.inputs.items():
            if available_resources.get(res, 0) < amount:
                return None

        for res, amount in recipe.inputs.items():
            available_resources[res] = available_resources.get(res, 0) - amount

        produced = {}
        for res, amount in recipe.outputs.items():
            final = amount + quality_bonus * amount * 0.5
            available_resources[res] = available_resources.get(res, 0) + final
            produced[res] = final

        recipe.times_used += 1
        return produced

    def get_innovations(self) -> list[Innovation]:
        return list(self._innovations)

    def get_innovation_stats(self) -> dict[str, Any]:
        return {
            "total_recipes": len(self._recipes),
            "total_innovations": len(self._innovations),
            "recipes_used": sum(1 for r in self._recipes.values() if r.times_used > 0),
            "average_efficiency": sum(r.efficiency for r in self._recipes.values()) / max(len(self._recipes), 1),
        }
