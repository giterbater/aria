from __future__ import annotations

import logging
import time
from typing import Any

from .interfaces import Skill, SkillResult
from .registry import SkillRegistry
from .router import SkillRouter

logger = logging.getLogger("aria.skills.manager")


class SkillManager:
    """High-level orchestrator that ties registry, router, and execution together.

    This is the entry point the Decision Engine uses to execute skills.
    It handles timing, logging, and result collection.
    """

    def __init__(self, registry: SkillRegistry | None = None) -> None:
        self._registry = registry or SkillRegistry()
        self._router = SkillRouter(self._registry)
        self._history: List[dict] = []

    @property
    def registry(self) -> SkillRegistry:
        return self._registry

    @property
    def router(self) -> SkillRouter:
        return self._router

    def register(self, skill: Skill) -> None:
        self._registry.register(skill)

    def execute(self, task: str, context: dict | None = None) -> SkillResult:
        """Execute a task by routing to appropriate skills."""
        t0 = time.monotonic()
        result = self._router.execute(task, context)
        elapsed = (time.monotonic() - t0) * 1000

        record = {
            "task": task,
            "success": result.success,
            "duration_ms": round(elapsed, 1),
            "skills": result.metadata.get("skills_executed", []),
            "errors": result.errors,
        }
        self._history.append(record)

        logger.info(
            "Skill execution: %s (success=%s, %.0fms, skills=%s)",
            task[:60], result.success, elapsed,
            record["skills"],
        )
        return result

    def execute_skill(self, name: str, **kwargs) -> SkillResult:
        """Execute a specific skill by name."""
        skill = self._registry.get(name)
        if skill is None:
            return SkillResult.fail(f"Skill not found: {name}")

        if not skill.validate(**kwargs):
            return SkillResult.fail(f"Validation failed for: {name}")

        t0 = time.monotonic()
        result = skill.execute(**kwargs)
        elapsed = (time.monotonic() - t0) * 1000

        self._history.append({
            "task": name,
            "success": result.success,
            "duration_ms": round(elapsed, 1),
            "skills": [name],
            "errors": result.errors,
        })
        return result

    def get_history(self, limit: int = 20) -> List[dict]:
        return self._history[-limit:]

    def summary(self) -> str:
        total = len(self._history)
        if total == 0:
            return "No skills executed yet."
        successes = sum(1 for h in self._history if h["success"])
        return f"Executions: {total} ({successes} success, {total - successes} failed)"
