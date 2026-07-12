"""Culture system — village-level knowledge, customs, and shared strategies.

The village develops customs over time.
Strategies are shared and inherited by new generations.
Culture emerges from collective experience.
"""

from __future__ import annotations

import random as _random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Custom:
    name: str
    description: str
    origin_agent: str
    day_established: int
    adherence: float = 0.5     # 0.0 = ignored, 1.0 = universally followed
    benefit: float = 0.0       # measured benefit to the village
    times_reinforced: int = 0

    @property
    def is_strong(self) -> bool:
        return self.adherence > 0.6 and self.times_reinforced > 3


@dataclass
class VillageStrategy:
    name: str
    description: str
    success_rate: float = 0.0
    times_used: int = 0
    origin_day: int = 0
    shared_by: list[str] = field(default_factory=list)

    @property
    def is_proven(self) -> bool:
        return self.times_used >= 5 and self.success_rate > 0.6


class CultureSystem:
    """Manages village-level culture, customs, and shared strategies."""

    CUSTOM_TEMPLATES = [
        {"name": "morning_gathering", "description": "Agents gather at dawn to share plans"},
        {"name": "resource_sharing", "description": "Surplus resources are shared with those in need"},
        {"name": "skill_rotation", "description": "Agents try different occupations periodically"},
        {"name": "elder_wisdom", "description": "Older agents' advice is given priority"},
        {"name": "group_hunting", "description": "Multiple hunters cooperate for better yields"},
        {"name": "trade_first", "description": "Trade before producing more"},
        {"name": "save_food", "description": "Keep food reserves for emergencies"},
        {"name": "teach_young", "description": "Experienced agents teach newcomers"},
    ]

    def __init__(self, rng: _random.Random | None = None) -> None:
        self._rng = rng or _random.Random()
        self._customs: list[Custom] = []
        self._strategies: dict[str, VillageStrategy] = {}
        self._village_knowledge: list[dict] = []

    def maybe_emerge_custom(self, day: int, trigger_event: str, agent_id: str) -> Custom | None:
        """A custom may emerge from a significant event."""
        if self._rng.random() > 0.15:
            return None

        template = self._rng.choice(self.CUSTOM_TEMPLATES)
        custom = Custom(
            name=template["name"],
            description=template["description"],
            origin_agent=agent_id,
            day_established=day,
            adherence=0.3,
        )
        self._customs.append(custom)
        return custom

    def reinforce_custom(self, custom_name: str, benefit: float = 0.1) -> None:
        for c in self._customs:
            if c.name == custom_name:
                c.adherence = min(1.0, c.adherence + 0.1)
                c.benefit += benefit
                c.times_reinforced += 1
                break

    def get_active_customs(self) -> list[Custom]:
        return [c for c in self._customs if c.adherence > 0.3]

    def get_custom(self, name: str) -> Custom | None:
        for c in self._customs:
            if c.name == name:
                return c
        return None

    def record_strategy(self, name: str, description: str, success: bool, agent_id: str, day: int) -> None:
        if name not in self._strategies:
            self._strategies[name] = VillageStrategy(
                name=name,
                description=description,
                origin_day=day,
            )
        s = self._strategies[name]
        s.times_used += 1
        if agent_id not in s.shared_by:
            s.shared_by.append(agent_id)
        total = s.times_used
        s.success_rate = (s.success_rate * (total - 1) + (1.0 if success else 0.0)) / total

    def get_proven_strategies(self) -> list[VillageStrategy]:
        return [s for s in self._strategies.values() if s.is_proven]

    def suggest_strategy(self, situation: str) -> VillageStrategy | None:
        """Suggest a proven strategy for a given situation."""
        proven = self.get_proven_strategies()
        if not proven:
            return None
        for s in proven:
            if situation.lower() in s.description.lower():
                return s
        return self._rng.choice(proven) if proven else None

    def add_village_knowledge(self, fact: str, source: str, day: int) -> None:
        self._village_knowledge.append({"fact": fact, "source": source, "day": day})

    def get_village_knowledge(self, limit: int = 10) -> list[dict]:
        return self._village_knowledge[-limit:]

    def get_culture_stats(self) -> dict[str, Any]:
        active = self.get_active_customs()
        proven = self.get_proven_strategies()
        return {
            "total_customs": len(self._customs),
            "active_customs": len(active),
            "strong_customs": sum(1 for c in active if c.is_strong),
            "total_strategies": len(self._strategies),
            "proven_strategies": len(proven),
            "village_knowledge_count": len(self._village_knowledge),
            "average_adherence": sum(c.adherence for c in active) / max(len(active), 1),
        }
