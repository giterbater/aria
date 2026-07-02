from __future__ import annotations

from .state import CognitiveState
from .needs import NeedSystem, Need


class DecisionBias:
    """Biases planning decisions based on internal state.

    Internal state should bias decisions, never directly execute actions.
    """

    def __init__(self, need_system: NeedSystem | None = None):
        self._needs = need_system or NeedSystem()

    def bias_plan(self, state: CognitiveState, plan_steps: list[dict], context: dict | None = None) -> list[dict]:
        """Apply cognitive bias to a plan's steps.

        Modifies step ordering, adds verification steps, adjusts confidence.
        """
        needs = self._needs.compute(state, context)
        needs_dict = {n.name: n for n in needs}

        biased = list(plan_steps)

        # High verification need → add verification steps
        if "verification" in needs_dict and needs_dict["verification"].strength > 0.6:
            for i, step in enumerate(biased):
                if step.get("risk") == "high":
                    biased.insert(i + 1, {
                        "id": f"verify_{step.get('id')}",
                        "skill": "code",
                        "action": "scan",
                        "args": {"path": "."},
                        "description": f"Verify results of: {step.get('description', '')}",
                        "dependencies": [step.get("id")],
                        "confidence": 0.9,
                        "risk": "low",
                        "rationale": "Added by caution bias — verify before proceeding",
                    })

        # High simplicity need → prefer shorter plans
        if "simplicity" in needs_dict and needs_dict["simplicity"].strength > 0.6:
            if len(biased) > 3:
                biased = biased[:3]
                biased.append({
                    "id": f"simple_{len(biased)}",
                    "skill": "reason",
                    "action": "",
                    "args": {},
                    "description": "Simplified approach due to high frustration",
                    "dependencies": [],
                    "confidence": 0.5,
                    "risk": "low",
                    "rationale": "Simplicity bias — truncated plan",
                })

        # High exploration need → add research step at start
        if "exploration" in needs_dict and needs_dict["exploration"].strength > 0.6:
            biased.insert(0, {
                "id": "explore_0",
                "skill": "code",
                "action": "scan",
                "args": {"path": "."},
                "description": "Explore codebase before acting",
                "dependencies": [],
                "confidence": 0.8,
                "risk": "low",
                "rationale": "Curiosity bias — gather information first",
            })

        # High recovery need → reset and replan
        if "recovery" in needs_dict and needs_dict["recovery"].strength > 0.5:
            biased.insert(0, {
                "id": "recover_0",
                "skill": "terminal",
                "action": "run",
                "args": {"command": "git status 2>&1"},
                "description": "Check repo state before recovery",
                "dependencies": [],
                "confidence": 0.9,
                "risk": "low",
                "rationale": "Recovery bias — assess current state",
            })

        return biased

    def should_ask_clarification(self, state: CognitiveState) -> bool:
        """Determine if ARIA should ask for clarification instead of proceeding."""
        return (
            state.confidence < 0.3
            or state.frustration > 0.8
            or state.consecutive_failures >= 5
        )

    def get_confidence_threshold(self, state: CognitiveState) -> float:
        """Get the confidence threshold for proceeding with execution.

        High caution → higher threshold (more careful).
        Low confidence → lower threshold (proceed despite uncertainty).
        """
        base = 0.5
        return base + (state.caution * 0.3) - ((1.0 - state.confidence) * 0.1)

    def get_retry_limit(self, state: CognitiveState) -> int:
        """Get how many retries are appropriate given current persistence."""
        if state.persistence > 0.8:
            return 5
        elif state.persistence > 0.5:
            return 3
        elif state.persistence > 0.3:
            return 2
        return 1
