"""Registry for benchmark tasks and suites."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger("aria.benchmarks.registry")


@dataclass
class BenchmarkTaskEntry:
    """A registered benchmark task."""
    name: str
    category: str
    description: str
    func: Callable[..., Any]
    weight: float = 1.0
    tags: list[str] = field(default_factory=list)


class BenchmarkRegistry:
    """Central registry for all benchmark tasks."""

    def __init__(self) -> None:
        self._tasks: dict[str, BenchmarkTaskEntry] = {}
        self._suites: dict[str, list[str]] = {}

    def register_task(
        self,
        name: str,
        category: str,
        description: str,
        func: Callable[..., Any],
        weight: float = 1.0,
        tags: list[str] | None = None,
    ) -> None:
        self._tasks[name] = BenchmarkTaskEntry(
            name=name, category=category, description=description,
            func=func, weight=weight, tags=tags or [],
        )
        logger.debug("Registered benchmark task: %s (%s)", name, category)

    def register_suite(self, suite_name: str, task_names: list[str]) -> None:
        self._suites[suite_name] = task_names
        logger.debug("Registered benchmark suite: %s with %d tasks", suite_name, len(task_names))

    def get_task(self, name: str) -> BenchmarkTaskEntry | None:
        return self._tasks.get(name)

    def get_suite_tasks(self, suite_name: str) -> list[BenchmarkTaskEntry]:
        task_names = self._suites.get(suite_name, [])
        return [self._tasks[n] for n in task_names if n in self._tasks]

    def list_tasks(self, category: str | None = None) -> list[BenchmarkTaskEntry]:
        tasks = list(self._tasks.values())
        if category:
            tasks = [t for t in tasks if t.category == category]
        return tasks

    def list_suites(self) -> list[str]:
        return list(self._suites.keys())

    def list_categories(self) -> list[str]:
        return sorted(set(t.category for t in self._tasks.values()))

    def count(self) -> int:
        return len(self._tasks)


_registry: BenchmarkRegistry | None = None


def get_registry() -> BenchmarkRegistry:
    global _registry
    if _registry is None:
        _registry = BenchmarkRegistry()
    return _registry


def register_default_tasks() -> BenchmarkRegistry:
    """Import and register all default benchmark tasks."""
    registry = get_registry()

    from .tasks.reasoning import register as reg_reasoning
    from .tasks.planning import register as reg_planning
    from .tasks.language import register as reg_language
    from .tasks.memory import register as reg_memory
    from .tasks.skills import register as reg_skills
    from .tasks.execution import register as reg_execution
    from .tasks.learning import register as reg_learning
    from .tasks.reflection import register as reg_reflection
    from .tasks.simulation import register as reg_simulation

    reg_reasoning(registry)
    reg_planning(registry)
    reg_language(registry)
    reg_memory(registry)
    reg_skills(registry)
    reg_execution(registry)
    reg_learning(registry)
    reg_reflection(registry)
    reg_simulation(registry)

    logger.info("Registered %d benchmark tasks across %d suites",
                registry.count(), len(registry.list_suites()))
    return registry
