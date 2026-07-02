from __future__ import annotations

import logging
from typing import List

from .knowledge import KnowledgeBase, KnowledgeEntry, KnowledgeType
from ..reflection.engine import ReflectionEngine
from ..reflection.interfaces import ReflectionType

logger = logging.getLogger("aria.learning")


class LearningEngine:
    """Processes reflections into persistent knowledge.

    Extracts patterns from reflections, builds a knowledge base,
    and provides relevant knowledge for future decisions.
    """

    def __init__(
        self,
        knowledge: KnowledgeBase | None = None,
        reflection: ReflectionEngine | None = None,
    ):
        self._knowledge = knowledge or KnowledgeBase()
        self._reflection = reflection

    @property
    def knowledge(self) -> KnowledgeBase:
        return self._knowledge

    def learn_from_reflections(self) -> int:
        """Process recent reflections into knowledge entries. Returns count of new entries."""
        if self._reflection is None:
            return 0

        reflections = self._reflection.get_reflections(limit=50)
        new_count = 0

        for reflection in reflections:
            for lesson in reflection.lessons:
                existing = self._find_similar(lesson.text)
                if existing:
                    self._knowledge.reinforce(existing.id, 0.05)
                else:
                    entry = KnowledgeEntry(
                        knowledge_type=self._type_from_reflection(reflection.reflection_type),
                        key=lesson.text[:100],
                        value=lesson.text,
                        confidence=lesson.confidence,
                        source=lesson.source,
                        tags=lesson.tags,
                    )
                    self._knowledge.store(entry)
                    new_count += 1

            if reflection.what_worked:
                for item in reflection.what_worked:
                    entry = KnowledgeEntry(
                        knowledge_type=KnowledgeType.SUCCESS_STRATEGY,
                        key=item[:100],
                        value=item,
                        source=reflection.summary,
                        tags=["success", "strategy"],
                    )
                    if not self._find_similar(item):
                        self._knowledge.store(entry)
                        new_count += 1

            if reflection.what_failed:
                for item in reflection.what_failed:
                    entry = KnowledgeEntry(
                        knowledge_type=KnowledgeType.FAILURE_MODE,
                        key=item[:100],
                        value=item,
                        source=reflection.summary,
                        tags=["failure", "mode"],
                    )
                    if not self._find_similar(item):
                        self._knowledge.store(entry)
                        new_count += 1

        if new_count > 0:
            logger.info("Learned %d new knowledge entries from %d reflections", new_count, len(reflections))

        return new_count

    def learn_from_skill_stats(self) -> int:
        """Build knowledge from skill success/failure statistics."""
        if self._reflection is None:
            return 0

        stats = self._reflection.get_skill_stats()
        new_count = 0

        for skill_name, skill_stats in stats.items():
            total = skill_stats["success"] + skill_stats["failure"]
            if total < 3:
                continue

            rate = skill_stats["success"] / total
            avg_ms = skill_stats["avg_ms"]

            if rate < 0.3:
                entry = KnowledgeEntry(
                    knowledge_type=KnowledgeType.FAILURE_MODE,
                    key=f"skill:{skill_name}:unreliable",
                    value=f"Skill '{skill_name}' fails {skill_stats['failure']}/{total} times. Consider alternatives.",
                    confidence=0.9,
                    tags=["skill", skill_name, "unreliable"],
                )
                if not self._find_similar(f"skill:{skill_name}:unreliable"):
                    self._knowledge.store(entry)
                    new_count += 1
            elif rate > 0.9:
                entry = KnowledgeEntry(
                    knowledge_type=KnowledgeType.SUCCESS_STRATEGY,
                    key=f"skill:{skill_name}:reliable",
                    value=f"Skill '{skill_name}' succeeds {skill_stats['success']}/{total} times. Prefer this skill.",
                    confidence=0.9,
                    tags=["skill", skill_name, "reliable"],
                )
                if not self._find_similar(f"skill:{skill_name}:reliable"):
                    self._knowledge.store(entry)
                    new_count += 1

            if avg_ms > 5000:
                entry = KnowledgeEntry(
                    knowledge_type=KnowledgeType.PATTERN,
                    key=f"skill:{skill_name}:slow",
                    value=f"Skill '{skill_name}' averages {avg_ms:.0f}ms. Consider caching or optimization.",
                    confidence=0.8,
                    tags=["skill", skill_name, "performance"],
                )
                if not self._find_similar(f"skill:{skill_name}:slow"):
                    self._knowledge.store(entry)
                    new_count += 1

        return new_count

    def learn_workflow(self, task: str, steps: list[str], success: bool) -> None:
        """Record a workflow pattern from experience."""
        workflow_key = f"workflow:{task[:50]}"
        status = "succeeded" if success else "failed"

        entry = KnowledgeEntry(
            knowledge_type=KnowledgeType.WORKFLOW,
            key=workflow_key,
            value=json.dumps({"task": task, "steps": steps, "status": status}),
            confidence=1.0 if success else 0.3,
            tags=["workflow", status],
        )
        existing = self._knowledge.get(workflow_key)
        if existing:
            if success:
                self._knowledge.reinforce(existing.id, 0.1)
            else:
                self._knowledge.weaken(existing.id, 0.1)
        else:
            self._knowledge.store(entry)

    def get_relevant_knowledge(self, query: str, limit: int = 10) -> List[KnowledgeEntry]:
        """Find knowledge relevant to a query."""
        results = self._knowledge.search(query, limit=limit)
        for entry in results:
            self._knowledge.record_use(entry.id)
        return results

    def get_successful_strategies(self, limit: int = 10) -> List[KnowledgeEntry]:
        return self._knowledge.get_by_type(KnowledgeType.SUCCESS_STRATEGY, limit)

    def get_failure_modes(self, limit: int = 10) -> List[KnowledgeEntry]:
        return self._knowledge.get_by_type(KnowledgeType.FAILURE_MODE, limit)

    def get_workflows(self, limit: int = 10) -> List[KnowledgeEntry]:
        return self._knowledge.get_by_type(KnowledgeType.WORKFLOW, limit)

    def get_knowledge_summary(self) -> str:
        counts = self._knowledge.count_by_type()
        total = self._knowledge.count()
        lines = [f"Knowledge base: {total} entries"]
        for ktype, count in sorted(counts.items()):
            lines.append(f"  {ktype}: {count}")
        return "\n".join(lines)

    def _find_similar(self, text: str) -> KnowledgeEntry | None:
        results = self._knowledge.search(text, limit=1)
        return results[0] if results else None

    def _type_from_reflection(self, rtype: ReflectionType) -> KnowledgeType:
        mapping = {
            ReflectionType.SUCCESS: KnowledgeType.SUCCESS_STRATEGY,
            ReflectionType.FAILURE: KnowledgeType.FAILURE_MODE,
            ReflectionType.IMPROVEMENT: KnowledgeType.PATTERN,
            ReflectionType.LEARNING: KnowledgeType.FACT,
            ReflectionType.OBSERVATION: KnowledgeType.FACT,
        }
        return mapping.get(rtype, KnowledgeType.FACT)


import json
