from __future__ import annotations

import logging
from typing import Dict, List

from .interfaces import Skill, SkillMeta

logger = logging.getLogger("aria.skills.registry")


class SkillRegistry:
    """Discovers, registers, and manages available skills.

    The Language Cortex queries this registry to find skills
    rather than hardcoding skill names.
    """

    def __init__(self) -> None:
        self._skills: Dict[str, Skill] = {}
        self._enabled: Dict[str, bool] = {}

    def register(self, skill: Skill) -> None:
        name = skill.meta.name
        self._skills[name] = skill
        self._enabled[name] = True
        logger.info("Registered skill: %s v%s", name, skill.meta.version)

    def unregister(self, name: str) -> None:
        self._skills.pop(name, None)
        self._enabled.pop(name, None)

    def get(self, name: str) -> Skill | None:
        if self._enabled.get(name, False):
            return self._skills.get(name)
        return None

    def list_skills(self, enabled_only: bool = True) -> List[SkillMeta]:
        result = []
        for name, skill in self._skills.items():
            if enabled_only and not self._enabled.get(name, False):
                continue
            result.append(skill.meta)
        return result

    def list_by_category(self, category: str) -> List[Skill]:
        return [
            s for s in self._skills.values()
            if s.meta.category == category and self._enabled.get(s.meta.name, False)
        ]

    def enable(self, name: str) -> bool:
        if name in self._skills:
            self._enabled[name] = True
            return True
        return False

    def disable(self, name: str) -> bool:
        if name in self._skills:
            self._enabled[name] = False
            return True
        return False

    def find_by_tags(self, tags: List[str]) -> List[Skill]:
        tag_set = set(tags)
        return [
            s for s in self._skills.values()
            if tag_set & set(s.meta.tags) and self._enabled.get(s.meta.name, False)
        ]

    def find_by_capability(self, description: str) -> List[Skill]:
        desc_lower = description.lower()
        return [
            s for s in self._skills.values()
            if desc_lower in s.meta.description.lower()
            or desc_lower in s.meta.name.lower()
            or any(desc_lower in t for t in s.meta.tags)
        ]

    @property
    def count(self) -> int:
        return sum(1 for v in self._enabled.values() if v)
