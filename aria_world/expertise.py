"""Expertise system — specialization and mastery over time.

Agents become experts at their occupation.
Expertise increases production quality.
Death of an expert creates a knowledge gap.
"""

from __future__ import annotations

import random as _random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillProfile:
    skill: str
    level: float = 0.0         # 0.0 = novice, 1.0 = master
    practice_count: int = 0
    successes: int = 0
    failures: int = 0
    days_practicing: int = 0
    best_streak: int = 0
    current_streak: int = 0

    @property
    def success_rate(self) -> float:
        total = self.successes + self.failures
        return self.successes / total if total > 0 else 0.0

    @property
    def mastery_title(self) -> str:
        if self.level >= 0.9:
            return "Master"
        if self.level >= 0.7:
            return "Expert"
        if self.level >= 0.5:
            return "Journeyman"
        if self.level >= 0.3:
            return "Apprentice"
        return "Novice"

    @property
    def production_multiplier(self) -> float:
        """Expertise multiplies production output."""
        return 1.0 + self.level * 2.0  # 1x at novice, 3x at master


class ExpertiseSystem:
    """Tracks and improves agent expertise over time."""

    def __init__(self, rng: _random.Random | None = None) -> None:
        self._rng = rng or _random.Random()
        self._profiles: dict[tuple[str, str], SkillProfile] = {}  # (agent_id, skill) → profile

    def get_profile(self, agent_id: str, skill: str) -> SkillProfile:
        key = (agent_id, skill)
        if key not in self._profiles:
            self._profiles[key] = SkillProfile(skill=skill)
        return self._profiles[key]

    def get_agent_profiles(self, agent_id: str) -> list[SkillProfile]:
        return [p for (aid, _), p in self._profiles.items() if aid == agent_id]

    def record_practice(self, agent_id: str, skill: str, success: bool) -> SkillProfile:
        """Record a practice attempt and update expertise."""
        profile = self.get_profile(agent_id, skill)
        profile.practice_count += 1
        profile.days_practicing += 1

        if success:
            profile.successes += 1
            profile.current_streak += 1
            profile.best_streak = max(profile.best_streak, profile.current_streak)
            growth = self._compute_growth(profile)
            profile.level = min(1.0, profile.level + growth)
        else:
            profile.failures += 1
            profile.current_streak = 0
            profile.level = max(0.0, profile.level - 0.01)

        return profile

    def _compute_growth(self, profile: SkillProfile) -> float:
        """Compute expertise growth based on current level and practice.

        Growth follows a logarithmic curve:
        - Easy to learn basics (fast growth at low level)
        - Hard to master (slow growth at high level)
        - Streak bonus encourages consistent practice
        """
        base_growth = 0.02 * (1.0 - profile.level * 0.8)
        streak_bonus = min(0.01, profile.current_streak * 0.002)
        practice_bonus = min(0.01, profile.practice_count * 0.0005)
        return base_growth + streak_bonus + practice_bonus

    def get_production_multiplier(self, agent_id: str, skill: str) -> float:
        return self.get_profile(agent_id, skill).production_multiplier

    def get_best_skill(self, agent_id: str) -> SkillProfile | None:
        profiles = self.get_agent_profiles(agent_id)
        if not profiles:
            return None
        return max(profiles, key=lambda p: p.level)

    def get_expert_agents(self, skill: str, min_level: float = 0.7) -> list[tuple[str, float]]:
        """Find all agents with expertise >= min_level in a skill."""
        experts = []
        for (aid, s), p in self._profiles.items():
            if s == skill and p.level >= min_level:
                experts.append((aid, p.level))
        return sorted(experts, key=lambda x: x[1], reverse=True)

    def record_death(self, agent_id: str) -> list[SkillProfile]:
        """Record the knowledge gap when an expert dies."""
        profiles = self.get_agent_profiles(agent_id)
        for p in profiles:
            p.level *= 0.3  # Knowledge partially lost
        return profiles

    def get_village_expertise_stats(self) -> dict[str, Any]:
        if not self._profiles:
            return {"total_profiles": 0, "by_skill": {}, "experts": 0}

        by_skill: dict[str, list[float]] = {}
        for (_, skill), p in self._profiles.items():
            by_skill.setdefault(skill, []).append(p.level)

        experts = sum(1 for p in self._profiles.values() if p.level >= 0.7)

        return {
            "total_profiles": len(self._profiles),
            "by_skill": {
                s: {"count": len(levels), "avg_level": sum(levels) / len(levels)}
                for s, levels in by_skill.items()
            },
            "experts": experts,
        }
