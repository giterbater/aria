from __future__ import annotations

import json
import logging
from typing import List

from .knowledge import KnowledgeBase, KnowledgeEntry, KnowledgeType
from .skill_tracker import SkillTracker, SkillProfile
from .workflow_learner import WorkflowLearner
from ..reflection.engine import ReflectionEngine
from ..reflection.interfaces import ReflectionType, SkillOutcome

logger = logging.getLogger("aria.learning")


class LearningEngine:
    """Enhanced learning engine with cognitive integration.

    Processes reflections into knowledge, tracks skill performance,
    learns workflows, and integrates with cognitive state.
    """

    def __init__(
        self,
        knowledge: KnowledgeBase | None = None,
        reflection: ReflectionEngine | None = None,
        db_path: str | None = None,
    ):
        self._knowledge = knowledge or KnowledgeBase(db_path=db_path)
        self._reflection = reflection
        self._skill_tracker = SkillTracker(db_path=db_path)
        self._workflow_learner = WorkflowLearner(self._knowledge)

    @property
    def knowledge(self) -> KnowledgeBase:
        return self._knowledge

    @property
    def skill_tracker(self) -> SkillTracker:
        return self._skill_tracker

    @property
    def workflow_learner(self) -> WorkflowLearner:
        return self._workflow_learner

    def learn_from_reflections(self) -> int:
        """Process recent reflections into knowledge entries."""
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
            logger.info("Learned %d new entries from %d reflections", new_count, len(reflections))

        return new_count

    def learn_from_skill_stats(self) -> int:
        """Build knowledge from skill performance statistics."""
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
                    value=f"Skill '{skill_name}' fails {skill_stats['failure']}/{total} times.",
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
                    value=f"Skill '{skill_name}' succeeds {skill_stats['success']}/{total} times.",
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
                    value=f"Skill '{skill_name}' averages {avg_ms:.0f}ms.",
                    confidence=0.8,
                    tags=["skill", skill_name, "performance"],
                )
                if not self._find_similar(f"skill:{skill_name}:slow"):
                    self._knowledge.store(entry)
                    new_count += 1

        return new_count

    def record_skill_use(self, outcome: SkillOutcome) -> None:
        """Record a skill execution for performance tracking."""
        self._skill_tracker.record(
            skill_name=outcome.skill_name,
            success=outcome.success,
            duration_ms=outcome.duration_ms,
            context=outcome.action,
        )

    def record_workflow(self, task: str, steps: list[str], success: bool, duration_ms: float = 0.0) -> None:
        """Record a workflow execution."""
        self._workflow_learner.record_workflow(task, steps, success, duration_ms)

    def get_relevant_knowledge(self, query: str, limit: int = 10) -> List[KnowledgeEntry]:
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

    def suggest_workflow(self, task: str) -> list[str] | None:
        return self._workflow_learner.suggest_workflow(task)

    def recommend_skill(self, task_keywords: list[str] | None = None) -> str | None:
        return self._skill_tracker.get_best_skill(task_keywords)

    def get_unreliable_skills(self) -> List[SkillProfile]:
        return self._skill_tracker.get_unreliable_skills()

    def get_slow_skills(self) -> List[SkillProfile]:
        return self._skill_tracker.get_slow_skills()

    def get_skill_profiles(self) -> List[SkillProfile]:
        return self._skill_tracker.get_all_profiles()

    def get_knowledge_summary(self) -> str:
        counts = self._knowledge.count_by_type()
        total = self._knowledge.count()
        skill_stats = self._skill_tracker.get_all_profiles()
        wf_stats = self._workflow_learner.get_workflow_stats()
        lines = [
            f"Knowledge: {total} entries",
            f"Skills tracked: {len(skill_stats)}",
            f"Workflows: {wf_stats['total_workflows']} ({wf_stats['success_rate']:.0%} success)",
        ]
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
