"""Prediction primitives for the cognitive completion milestone."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Prediction:
    """A lightweight prediction for the likely outcome of an action."""

    action_type: str
    predicted_outcome: str
    predicted_reward: float
    confidence: float
    model_id: str = "heuristic-v0"
    rationale: str = ""
    state_features: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "predicted_outcome": self.predicted_outcome,
            "predicted_reward": self.predicted_reward,
            "confidence": self.confidence,
            "model_id": self.model_id,
            "rationale": self.rationale,
            "state_features": dict(self.state_features),
        }


class PredictionModel:
    """Deterministic prediction stub with a stable event shape.

    This is intentionally not an ML model. It gives the rest of the cognitive
    OS a production-shaped prediction object that can be replaced later.
    """

    model_id = "heuristic-v0"

    def predict(
        self,
        *,
        action_type: str,
        scores: dict[str, float],
        structured_input: Any = None,
        memory_matches: int = 0,
        active_goals: int = 0,
    ) -> Prediction:
        best_score = max(scores.values()) if scores else 0.0
        chosen_score = scores.get(action_type, best_score)
        score_share = chosen_score / best_score if best_score > 0 else 0.5
        confidence = max(0.0, min(1.0, score_share))

        predicted_reward = max(-1.0, min(1.0, (chosen_score - 0.5) / 3.0))
        predicted_outcome = "success" if predicted_reward >= 0.25 else "partial"
        if confidence < 0.35:
            predicted_outcome = "uncertain"

        intent = getattr(structured_input, "intent", "")
        rationale = (
            f"{action_type} scored {chosen_score:.2f}; "
            f"intent={intent or 'unknown'}, memories={memory_matches}, goals={active_goals}"
        )

        return Prediction(
            action_type=action_type,
            predicted_outcome=predicted_outcome,
            predicted_reward=round(predicted_reward, 4),
            confidence=round(confidence, 4),
            model_id=self.model_id,
            rationale=rationale,
            state_features={
                "intent": intent,
                "memory_matches": memory_matches,
                "active_goals": active_goals,
                "score": chosen_score,
            },
        )

    def surprise(self, prediction: Prediction, *, actual_outcome: str, reward: float) -> float:
        outcome_delta = 0.0 if prediction.predicted_outcome == actual_outcome else 0.5
        reward_delta = min(1.0, abs(prediction.predicted_reward - reward))
        return max(0.0, min(1.0, outcome_delta + reward_delta * 0.5))
