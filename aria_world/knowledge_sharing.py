"""Trust-based knowledge sharing and teaching system.

When agents interact, trust determines what knowledge gets shared.
Older/experienced agents teach younger ones.
Knowledge compounds across generations.
"""

from __future__ import annotations

import random as _random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Knowledge:
    id: str
    skill: str          # "farming", "hunting", "building", etc.
    level: float        # 0.0 = novice, 1.0 = master
    source: str         # agent_id who discovered/taught it
    day_discovered: int = 0
    times_used: int = 0
    times_taught: int = 0
    tags: list[str] = field(default_factory=list)


@dataclass
class TeachingEvent:
    teacher_id: str
    student_id: str
    knowledge_id: str
    skill: str
    trust_level: float
    success: bool
    day: int


class KnowledgeSharingSystem:
    """Manages knowledge transfer between agents based on trust."""

    def __init__(self, rng: _random.Random | None = None) -> None:
        self._rng = rng or _random.Random()
        self._knowledge: dict[str, Knowledge] = {}  # id → Knowledge
        self._agent_knowledge: dict[str, list[str]] = {}  # agent_id → [knowledge_ids]
        self._teaching_log: list[TeachingEvent] = []
        self._next_id = 0

    def _gen_id(self) -> str:
        self._next_id += 1
        return f"k{self._next_id}"

    def add_knowledge(self, agent_id: str, skill: str, level: float = 0.3, tags: list[str] | None = None) -> Knowledge:
        k = Knowledge(
            id=self._gen_id(),
            skill=skill,
            level=level,
            source=agent_id,
            tags=tags or [skill],
        )
        self._knowledge[k.id] = k
        self._agent_knowledge.setdefault(agent_id, []).append(k.id)
        return k

    def get_knowledge(self, k_id: str) -> Knowledge | None:
        return self._knowledge.get(k_id)

    def get_agent_knowledge(self, agent_id: str) -> list[Knowledge]:
        k_ids = self._agent_knowledge.get(agent_id, [])
        return [self._knowledge[kid] for kid in k_ids if kid in self._knowledge]

    def get_agent_skill_level(self, agent_id: str, skill: str) -> float:
        """Get the agent's best knowledge level for a skill."""
        knowledge = self.get_agent_knowledge(agent_id)
        skill_knowledge = [k for k in knowledge if k.skill == skill]
        if not skill_knowledge:
            return 0.0
        return max(k.level for k in skill_knowledge)

    def attempt_teaching(
        self,
        teacher_id: str,
        student_id: str,
        trust_level: float,
        day: int,
    ) -> TeachingEvent | None:
        """Attempt to teach a student based on trust level.

        Trust determines:
        - Whether teaching happens (trust > 30)
        - What knowledge is shared (higher trust = better knowledge)
        - Success probability (trust * 0.01 base)
        """
        if trust_level < 30:
            return None

        teacher_knowledge = self.get_agent_knowledge(teacher_id)
        if not teacher_knowledge:
            return None

        best_k = max(teacher_knowledge, key=lambda k: k.level)

        share_threshold = max(0.0, 1.0 - (trust_level / 100.0))
        if best_k.level < share_threshold:
            return None

        success_chance = min(0.9, trust_level * 0.008 + best_k.level * 0.2)
        success = self._rng.random() < success_chance

        event = TeachingEvent(
            teacher_id=teacher_id,
            student_id=student_id,
            knowledge_id=best_k.id,
            skill=best_k.skill,
            trust_level=trust_level,
            success=success,
            day=day,
        )
        self._teaching_log.append(event)

        if success:
            taught_level = best_k.level * 0.6 * (trust_level / 100.0)
            new_k = self.add_knowledge(
                student_id,
                best_k.skill,
                level=taught_level,
                tags=best_k.tags + ["taught"],
            )
            best_k.times_taught += 1
            return event

        return event

    def improve_knowledge(self, agent_id: str, skill: str, delta: float = 0.05) -> None:
        """Improve an agent's knowledge through practice."""
        knowledge = self.get_agent_knowledge(agent_id)
        for k in knowledge:
            if k.skill == skill:
                k.level = min(1.0, k.level + delta)
                k.times_used += 1

    def decay_knowledge(self, agent_id: str, decay_rate: float = 0.01) -> None:
        """Slowly decay unused knowledge."""
        knowledge = self.get_agent_knowledge(agent_id)
        for k in knowledge:
            if k.times_used == 0:
                k.level = max(0.0, k.level - decay_rate)

    def get_village_knowledge_stats(self) -> dict[str, Any]:
        if not self._knowledge:
            return {"total": 0, "by_skill": {}, "average_level": 0.0}

        by_skill: dict[str, list[float]] = {}
        for k in self._knowledge.values():
            by_skill.setdefault(k.skill, []).append(k.level)

        return {
            "total": len(self._knowledge),
            "by_skill": {s: {"count": len(levels), "avg_level": sum(levels) / len(levels)} for s, levels in by_skill.items()},
            "average_level": sum(k.level for k in self._knowledge.values()) / len(self._knowledge),
            "total_teachings": len(self._teaching_log),
            "successful_teachings": sum(1 for t in self._teaching_log if t.success),
        }

    @property
    def teaching_log(self) -> list[TeachingEvent]:
        return list(self._teaching_log)
