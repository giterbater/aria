"""Outcome to learning loop for ARIA cognition."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aria_core.memory.interfaces import MemorySystemProtocol
from aria_core.memory.models import Outcome

from .events import CognitiveEvent, Event


@dataclass(frozen=True)
class ObservedOutcome:
    """Execution feedback for one cognitive episode."""

    episode_id: str
    agent_id: str
    result: str
    reward: float = 0.0
    surprise: float = 0.0
    tick: int = 0
    delta_prediction: dict[str, Any] = field(default_factory=dict)
    notes: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "result": self.result,
            "reward": self.reward,
            "surprise": self.surprise,
            "delta_prediction": dict(self.delta_prediction),
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }


class OutcomeLearningLoop:
    """Records outcomes into memory and emits the Learning event."""

    def __init__(self, memory: MemorySystemProtocol, event_bus: Any | None = None) -> None:
        self._memory = memory
        if event_bus is None:
            from event_bus import bus

            event_bus = bus
        self._bus = event_bus
        self._subscribed = False

    def subscribe(self) -> None:
        if not self._subscribed:
            self._bus.subscribe(Event.OUTCOME, self.learn_from_outcome)
            self._subscribed = True

    def unsubscribe(self) -> None:
        if self._subscribed:
            self._bus.unsubscribe(Event.OUTCOME, self.learn_from_outcome)
            self._subscribed = False

    def observe_outcome(self, outcome: ObservedOutcome) -> CognitiveEvent:
        outcome_event = CognitiveEvent(
            episode_id=outcome.episode_id,
            agent_id=outcome.agent_id,
            event=Event.OUTCOME,
            tick=outcome.tick,
            sequence=7,
            payload=outcome.to_payload(),
        )
        self._bus.publish(Event.OUTCOME, outcome_event)
        if not self._subscribed:
            return self.learn_from_outcome(outcome_event)
        return outcome_event

    def learn_from_outcome(self, event: CognitiveEvent) -> CognitiveEvent:
        payload = event.payload
        outcome = _classify_outcome(payload.get("result"), float(payload.get("reward", 0.0)))
        delta = _importance_delta(outcome)
        notes = payload.get("notes")

        try:
            self._memory.record_outcome(event.episode_id, outcome, notes=notes)
        except NotImplementedError:
            self._memory.update_importance(event.episode_id, delta)

        learning_event = CognitiveEvent(
            episode_id=event.episode_id,
            agent_id=event.agent_id,
            event=Event.LEARNING,
            tick=event.tick,
            sequence=8,
            payload={
                "memory_updates": [
                    {
                        "item_id": event.episode_id,
                        "delta": delta,
                        "reason": f"Outcome classified as {outcome.value}",
                    }
                ],
                "influence_shift": delta,
                "skill_delta": {},
                "outcome": outcome.value,
            },
        )
        self._bus.publish(Event.LEARNING, learning_event)
        return learning_event


def _classify_outcome(result: Any, reward: float) -> Outcome:
    if isinstance(result, Outcome):
        return result
    normalized = str(result or "").lower()
    if normalized in {item.value for item in Outcome}:
        return Outcome(normalized)
    if normalized in {"ok", "true", "done", "completed"}:
        return Outcome.SUCCESS
    if normalized in {"fail", "failure", "error", "false"}:
        return Outcome.FAILED
    if reward > 0.1:
        return Outcome.SUCCESS
    if reward < -0.1:
        return Outcome.FAILED
    return Outcome.PARTIAL


def _importance_delta(outcome: Outcome) -> float:
    if outcome == Outcome.SUCCESS:
        return 0.10
    if outcome == Outcome.CORRECTED:
        return 0.05
    if outcome in {Outcome.FAILED, Outcome.IGNORED}:
        return -0.05
    return 0.0
