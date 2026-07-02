from __future__ import annotations

import logging
from typing import List

from .interfaces import Skill, SkillResult
from .registry import SkillRegistry

logger = logging.getLogger("aria.skills.router")


class SkillRouter:
    """Determines which skills to execute and in what order.

    The Language Cortex calls the router to translate a high-level
    objective into an ordered sequence of skill invocations.
    """

    def __init__(self, registry: SkillRegistry) -> None:
        self._registry = registry

    def resolve(self, task: str, context: dict | None = None) -> List[Skill]:
        """Find skills that can handle the given task description."""
        candidates = self._registry.find_by_capability(task)
        if candidates:
            return candidates

        keywords = task.lower().split()
        for keyword in keywords:
            matches = self._registry.find_by_capability(keyword)
            if matches:
                return matches

        return []

    def order_by_dependencies(self, skills: List[Skill]) -> List[Skill]:
        """Topological sort by skill dependencies."""
        name_to_skill = {s.meta.name: s for s in skills}
        visited: set[str] = set()
        ordered: List[Skill] = []

        def _visit(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            skill = name_to_skill.get(name)
            if skill is None:
                return
            for dep in skill.meta.dependencies:
                _visit(dep)
            ordered.append(skill)

        for skill in skills:
            _visit(skill.meta.name)

        return ordered

    def can_parallel(self, skills: List[Skill]) -> List[List[Skill]]:
        """Group skills into parallelizable batches.

        Skills with no dependencies on each other can run in parallel.
        Returns a list of batches, each batch is a list of skills.
        """
        name_to_skill = {s.meta.name: s for s in skills}
        remaining = set(name_to_skill.keys())
        batches: List[List[Skill]] = []

        while remaining:
            ready = []
            for name in list(remaining):
                skill = name_to_skill[name]
                deps = set(skill.meta.dependencies) & remaining
                if not deps:
                    ready.append(skill)

            if not ready:
                logger.warning("Circular dependency detected, breaking with remaining: %s", remaining)
                ready = [name_to_skill[n] for n in remaining]

            batches.append(ready)
            for s in ready:
                remaining.discard(s.meta.name)

        return batches

    def execute(self, task: str, context: dict | None = None) -> SkillResult:
        """Resolve, order, and execute skills for a task."""
        skills = self.resolve(task, context)
        if not skills:
            return SkillResult.fail(f"No skills found for: {task}")

        ordered = self.order_by_dependencies(skills)
        results = []

        for skill in ordered:
            if not skill.validate(**(context or {})):
                results.append(SkillResult.fail(
                    f"Validation failed for {skill.meta.name}",
                    skill=skill.meta.name,
                ))
                continue

            result = skill.execute(**(context or {}))
            results.append(result)

            if not result.success:
                logger.warning("Skill %s failed: %s", skill.meta.name, result.errors)
                break

        all_success = all(r.success for r in results)
        combined_output = [r.output for r in results if r.output is not None]
        combined_errors = [e for r in results for e in r.errors]
        combined_warnings = [w for r in results for w in r.warnings]

        return SkillResult(
            success=all_success,
            output=combined_output if len(combined_output) != 1 else combined_output[0],
            warnings=combined_warnings,
            errors=combined_errors,
            metadata={"skills_executed": [s.meta.name for s in ordered]},
        )
