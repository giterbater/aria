from __future__ import annotations

import logging
from typing import List

from .knowledge import KnowledgeBase, KnowledgeEntry, KnowledgeType
from .engine import LearningEngine

logger = logging.getLogger("aria.learning.influence")


class DecisionInfluencer:
    """Provides learned knowledge to the decision engine.

    When the CTO plans or decides, this component supplies context
    from past experience: what worked, what failed, which skills to use.
    """

    def __init__(self, learning: LearningEngine):
        self._learning = learning

    def get_context_for_task(self, task: str) -> dict:
        """Build a knowledge context dict for a task.

        Returns a dict with:
        - strategies: successful approaches for similar tasks
        - warnings: failure modes to avoid
        - preferred_skills: skills with high success rates
        - workflows: proven workflows for this task type
        """
        relevant = self._learning.get_relevant_knowledge(task, limit=10)

        strategies = []
        warnings = []
        preferred = []
        workflows = []

        for entry in relevant:
            if entry.knowledge_type == KnowledgeType.SUCCESS_STRATEGY:
                strategies.append(entry.value)
            elif entry.knowledge_type == KnowledgeType.FAILURE_MODE:
                warnings.append(entry.value)
            elif entry.knowledge_type == KnowledgeType.WORKFLOW:
                try:
                    wf = __import__("json").loads(entry.value)
                    workflows.append(wf)
                except (json.JSONDecodeError, TypeError):
                    pass
            elif "skill" in entry.tags and "reliable" in entry.tags:
                preferred.append(entry.key.split(":")[1] if ":" in entry.key else entry.key)

        return {
            "strategies": strategies,
            "warnings": warnings,
            "preferred_skills": preferred,
            "workflows": workflows,
        }

    def should_use_skill(self, skill_name: str) -> tuple[bool, str]:
        """Check if a skill is recommended based on learned knowledge."""
        entries = self._learning.get_relevant_knowledge(f"skill:{skill_name}", limit=5)

        for entry in entries:
            if "reliable" in entry.tags:
                return True, f"Skill '{skill_name}' has proven reliable ({entry.value})"
            if "unreliable" in entry.tags:
                return False, f"Skill '{skill_name}' has been unreliable ({entry.value})"

        return True, f"No strong evidence against '{skill_name}'"

    def get_workflow_suggestion(self, task: str) -> list[str] | None:
        """Suggest a workflow based on learned patterns."""
        workflows = self._learning.get_workflows(limit=10)

        task_lower = task.lower()
        best_match = None
        best_score = 0

        for wf_entry in workflows:
            try:
                wf = __import__("json").loads(wf_entry.value)
                wf_task = wf.get("task", "").lower()
                wf_status = wf.get("status", "")

                if wf_status != "succeeded":
                    continue

                task_tokens = set(task_lower.split())
                wf_tokens = set(wf_task.split())
                overlap = len(task_tokens & wf_tokens)
                score = overlap * wf_entry.confidence

                if score > best_score:
                    best_score = score
                    best_match = wf.get("steps", [])
            except (json.JSONDecodeError, TypeError, KeyError):
                continue

        return best_match if best_score > 0 else None

    def build_recommendation_prompt(self, task: str) -> str:
        """Build a prompt section with learned knowledge for the LLM."""
        context = self.get_context_for_task(task)
        parts = []

        if context["strategies"]:
            parts.append("Past strategies that worked:")
            for s in context["strategies"][:3]:
                parts.append(f"  - {s}")

        if context["warnings"]:
            parts.append("Known failure modes to avoid:")
            for w in context["warnings"][:3]:
                parts.append(f"  - {w}")

        if context["preferred_skills"]:
            parts.append(f"Recommended skills: {', '.join(context['preferred_skills'])}")

        if context["workflows"]:
            wf = context["workflows"][0]
            steps = wf.get("steps", [])
            if steps:
                parts.append(f"Proven workflow: {' -> '.join(steps[:5])}")

        return "\n".join(parts) if parts else ""


import json
