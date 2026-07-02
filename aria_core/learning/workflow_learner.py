from __future__ import annotations

import json
import logging
from typing import List

from .knowledge import KnowledgeBase, KnowledgeEntry, KnowledgeType

logger = logging.getLogger("aria.learning.workflow")


class WorkflowLearner:
    """Learns and suggests workflows from experience.

    Tracks successful task sequences and recommends them
    for similar future tasks.
    """

    def __init__(self, knowledge: KnowledgeBase):
        self._knowledge = knowledge

    def record_workflow(self, task: str, steps: list[str], success: bool, duration_ms: float = 0.0) -> None:
        """Record a workflow execution."""
        key = f"workflow:{task[:80]}"
        value = json.dumps({
            "task": task,
            "steps": steps,
            "success": success,
            "duration_ms": duration_ms,
        })

        existing = self._knowledge.get(key)
        if existing:
            if success:
                self._knowledge.reinforce(existing.id, 0.1)
            else:
                self._knowledge.weaken(existing.id, 0.1)
        else:
            entry = KnowledgeEntry(
                knowledge_type=KnowledgeType.WORKFLOW,
                key=key,
                value=value,
                confidence=1.0 if success else 0.3,
                tags=["workflow", "success" if success else "failure"],
            )
            self._knowledge.store(entry)

    def suggest_workflow(self, task: str) -> list[str] | None:
        """Suggest a workflow based on past experience."""
        workflows = self._knowledge.get_by_type(KnowledgeType.WORKFLOW, limit=50)

        task_tokens = set(task.lower().split())
        best_match = None
        best_score = 0.0

        for entry in workflows:
            try:
                data = json.loads(entry.value)
                wf_task = data.get("task", "").lower()
                wf_tokens = set(wf_task.split())
                overlap = len(task_tokens & wf_tokens)
                score = overlap * entry.confidence
                if score > best_score:
                    best_score = score
                    best_match = data.get("steps", [])
            except (json.JSONDecodeError, TypeError):
                continue

        return best_match if best_score > 0 else None

    def get_similar_tasks(self, task: str, limit: int = 5) -> list[dict]:
        """Find similar tasks that have been executed before."""
        workflows = self._knowledge.get_by_type(KnowledgeType.WORKFLOW, limit=50)
        task_tokens = set(task.lower().split())

        scored = []
        for entry in workflows:
            try:
                data = json.loads(entry.value)
                wf_tokens = set(data.get("task", "").lower().split())
                overlap = len(task_tokens & wf_tokens)
                if overlap > 0:
                    scored.append({
                        "task": data.get("task", ""),
                        "steps": data.get("steps", []),
                        "success": data.get("success", False),
                        "score": overlap * entry.confidence,
                    })
            except (json.JSONDecodeError, TypeError):
                continue

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    def get_workflow_stats(self) -> dict:
        """Get statistics about learned workflows."""
        workflows = self._knowledge.get_by_type(KnowledgeType.WORKFLOW, limit=100)
        total = len(workflows)
        successful = 0
        for entry in workflows:
            try:
                data = json.loads(entry.value)
                if data.get("success"):
                    successful += 1
            except (json.JSONDecodeError, TypeError):
                continue

        return {
            "total_workflows": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": successful / total if total > 0 else 0.0,
        }
