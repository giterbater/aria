from __future__ import annotations

import logging
from typing import Dict

from .interfaces import SpecialistRequest, SpecialistResponse
from .subprocess_agent import SubprocessAgent

logger = logging.getLogger("aria.cto.delegation")


class SpecialistManager:
    """Manages specialist selection and delegation."""

    SPECIALIST_PROFILES: Dict[str, list[str]] = {
        "mimo": [
            "core", "architecture", "data structures", "memory", "persistence",
            "interfaces", "protocols", "design patterns", "config", "models",
        ],
        "nemotron": [
            "testing", "integration", "input", "output", "language model",
            "UI", "events", "pipeline", "regression", "fix",
        ],
    }

    def __init__(self, agent: SubprocessAgent | None = None) -> None:
        self._agent = agent or SubprocessAgent()
        self._profiles = dict(self.SPECIALIST_PROFILES)

    def select_specialist(self, task_description: str) -> str:
        """Select the best specialist for a task based on keyword matching."""
        task_lower = task_description.lower()
        scores: Dict[str, int] = {}

        for name, keywords in self._profiles.items():
            score = sum(1 for kw in keywords if kw in task_lower)
            scores[name] = score

        best = max(scores, key=scores.get)  # type: ignore[arg-type]
        if scores[best] == 0:
            return "mimo"  # default to mimo if no keywords match

        return best

    def delegate(self, request: SpecialistRequest) -> SpecialistResponse:
        """Delegate a task to the specified specialist."""
        logger.info(
            "Delegating to %s: %s",
            request.specialist_name,
            request.task_description[:100],
        )

        response = self._agent.spawn(request)

        logger.info(
            "Specialist %s returned: %s",
            request.specialist_name,
            response.status,
        )

        return response

    def delegate_auto(self, task_description: str, **kwargs) -> SpecialistResponse:
        """Auto-select specialist and delegate."""
        name = self.select_specialist(task_description)
        request = SpecialistRequest(
            specialist_name=name,
            task_description=task_description,
            **kwargs,
        )
        return self.delegate(request)
