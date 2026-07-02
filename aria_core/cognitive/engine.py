from __future__ import annotations

import logging
from typing import Any

from .state import InternalState, CognitiveState
from .needs import NeedSystem, Need
from .bias import DecisionBias
from .metrics import CognitiveMetrics, MetricsTracker
from ..reasoning import ReasoningEngine, ReasoningContext, ReasonedPlan

logger = logging.getLogger("aria.cognitive")


class CognitiveEngine:
    """Integrates internal state into the reasoning pipeline.

    Architecture:
    Reasoning Engine → gather context → apply cognitive bias → produce plan

    The cognitive engine does NOT execute actions.
    It biases the reasoning engine's decisions based on internal state.
    """

    def __init__(
        self,
        reasoning: ReasoningEngine,
        internal_state: InternalState | None = None,
        db_path: str | None = None,
    ):
        self._reasoning = reasoning
        self._state = internal_state or InternalState(db_path=db_path)
        self._needs = NeedSystem()
        self._bias = DecisionBias(self._needs)
        self._metrics = MetricsTracker(db_path=db_path)

    @property
    def state(self) -> CognitiveState:
        return self._state.get_state()

    @property
    def metrics(self) -> MetricsTracker:
        return self._metrics

    def reason(self, objective: str, context: ReasoningContext | None = None) -> ReasonedPlan:
        """Reason about an objective with cognitive bias applied."""
        if context is None:
            context = ReasoningContext(objective=objective)

        cognitive_state = self._state.get_state()
        needs = self._needs.compute(cognitive_state, {"objective": objective})

        if self._bias.should_ask_clarification(cognitive_state):
            logger.info("Low confidence (%.0f%%) — should ask for clarification",
                        cognitive_state.confidence * 100)

        plan = self._reasoning.reason(objective, context)

        biased_steps = self._bias.bias_plan(cognitive_state, plan.steps, {"objective": objective})
        plan.steps = biased_steps

        plan.confidence.goal = min(1.0, plan.confidence.goal + cognitive_state.confidence * 0.1)

        logger.info(
            "Cognitive reasoning: confidence=%.0f%%, needs=%s, steps=%d",
            cognitive_state.confidence * 100,
            [n.name for n in needs],
            len(plan.steps),
        )
        return plan

    def update_from_outcome(self, success: bool, context: dict | None = None) -> CognitiveState:
        """Update internal state after a task outcome."""
        return self._state.update_from_outcome(success, context)

    def update_from_reflection(self, reflection_type: str, lessons_count: int) -> CognitiveState:
        """Update internal state after reflection."""
        return self._state.update_from_reflection(reflection_type, lessons_count)

    def get_needs(self) -> list[Need]:
        """Get current needs based on internal state."""
        return self._needs.compute(self._state.get_state())

    def should_retry(self) -> bool:
        """Determine if another retry is appropriate."""
        state = self._state.get_state()
        limit = self._bias.get_retry_limit(state)
        return state.consecutive_failures < limit

    def get_confidence_threshold(self) -> float:
        return self._bias.get_confidence_threshold(self._state.get_state())

    def record_benchmark(self, name: str, metrics: CognitiveMetrics, state_enabled: bool) -> None:
        metrics.compute_overall()
        self._metrics.record_run(name, metrics, state_enabled)

    def get_benchmark_comparison(self, name: str) -> dict:
        return self._metrics.get_comparison(name)

    def get_status(self) -> dict:
        state = self._state.get_state()
        needs = self.get_needs()
        return {
            "state": state.to_dict(),
            "needs": [{"name": n.name, "strength": n.strength, "reason": n.reason} for n in needs],
            "should_ask": self._bias.should_ask_clarification(state),
            "confidence_threshold": self._bias.get_confidence_threshold(state),
            "retry_limit": self._bias.get_retry_limit(state),
        }

    def shutdown(self) -> None:
        self._state.close()
        self._metrics.close()
