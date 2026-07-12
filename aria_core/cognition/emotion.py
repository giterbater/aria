"""Emotion state with auditable cause explanations."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque

from .events import CognitiveEvent, Event

EMOTION_DIMS = (
    "confidence",
    "curiosity",
    "frustration",
    "motivation",
    "caution",
    "persistence",
    "novelty",
)


@dataclass(frozen=True)
class EmotionDelta:
    dim: str
    delta: float
    cause_episode_id: str
    cause_event: str
    cause_text: str


@dataclass
class EmotionState:
    values: dict[str, float] = field(default_factory=lambda: {dim: 0.5 for dim in EMOTION_DIMS})
    recent: Deque[EmotionDelta] = field(default_factory=lambda: deque(maxlen=32))

    def apply(self, delta: EmotionDelta) -> None:
        if delta.dim not in self.values:
            return
        old = self.values[delta.dim]
        self.values[delta.dim] = max(0.0, min(1.0, old + delta.delta))
        self.recent.appendleft(delta)

    def explain(self, dim: str) -> list[EmotionDelta]:
        return [delta for delta in self.recent if delta.dim == dim]


class EmotionAttributor:
    """Maps cognitive events to emotion deltas and publishes explanations."""

    def __init__(self, state: EmotionState | None = None, event_bus: Any | None = None) -> None:
        self.state = state or EmotionState()
        if event_bus is None:
            from event_bus import bus

            event_bus = bus
        self._bus = event_bus
        self._subscribed = False

    def subscribe(self) -> None:
        if self._subscribed:
            return
        self._bus.subscribe(Event.OUTCOME, self.handle_event)
        self._bus.subscribe(Event.OBSERVATION, self.handle_event)
        self._bus.subscribe(Event.LEARNING, self.handle_event)
        self._subscribed = True

    def unsubscribe(self) -> None:
        if not self._subscribed:
            return
        self._bus.unsubscribe(Event.OUTCOME, self.handle_event)
        self._bus.unsubscribe(Event.OBSERVATION, self.handle_event)
        self._bus.unsubscribe(Event.LEARNING, self.handle_event)
        self._subscribed = False

    def handle_event(self, event: CognitiveEvent) -> CognitiveEvent | None:
        deltas = self._deltas_for(event)
        if not deltas:
            return None

        before = dict(self.state.values)
        for delta in deltas:
            self.state.apply(delta)
        changed = {
            dim: self.state.values[dim] - before[dim]
            for dim in self.state.values
            if self.state.values[dim] != before[dim]
        }
        causes = {delta.dim: delta.cause_text for delta in deltas}

        emotion_event = CognitiveEvent(
            episode_id=event.episode_id,
            agent_id=event.agent_id,
            event=Event.EMOTION,
            tick=event.tick,
            sequence=9,
            payload={
                "state": dict(self.state.values),
                "delta": changed,
                "cause": causes,
            },
        )
        self._bus.publish(Event.EMOTION, emotion_event)
        return emotion_event

    def _deltas_for(self, event: CognitiveEvent) -> list[EmotionDelta]:
        if event.event == Event.OUTCOME:
            return self._outcome_deltas(event)
        if event.event == Event.OBSERVATION:
            return self._observation_deltas(event)
        if event.event == Event.LEARNING:
            return self._learning_deltas(event)
        return []

    def _outcome_deltas(self, event: CognitiveEvent) -> list[EmotionDelta]:
        payload = event.payload
        result = str(payload.get("result", "")).lower()
        reward = float(payload.get("reward", 0.0))
        surprise = float(payload.get("surprise", 0.0))
        deltas: list[EmotionDelta] = []

        if surprise > 0.5:
            deltas.append(
                EmotionDelta(
                    "confidence",
                    -0.1 * surprise,
                    event.episode_id,
                    event.event,
                    "Prediction failed: observed outcome diverged from expectation.",
                )
            )
        elif result in {"success", "corrected"} or reward > 0.1:
            deltas.append(
                EmotionDelta(
                    "confidence",
                    0.05,
                    event.episode_id,
                    event.event,
                    "Prediction matched or reward was positive.",
                )
            )

        if result in {"success", "corrected"} or reward > 0.1:
            deltas.append(
                EmotionDelta(
                    "persistence",
                    0.05,
                    event.episode_id,
                    event.event,
                    "Approach worked for this episode.",
                )
            )
            deltas.append(
                EmotionDelta(
                    "frustration",
                    -0.05,
                    event.episode_id,
                    event.event,
                    "Successful outcome reduced recent failure pressure.",
                )
            )
        elif result in {"failed", "failure"} or reward < -0.1:
            deltas.append(
                EmotionDelta(
                    "frustration",
                    0.15,
                    event.episode_id,
                    event.event,
                    "Outcome failed or reward was negative.",
                )
            )

        if payload.get("danger") is True or payload.get("metadata", {}).get("danger") is True:
            deltas.append(
                EmotionDelta(
                    "caution",
                    0.1,
                    event.episode_id,
                    event.event,
                    "Threat detected in outcome metadata.",
                )
            )

        return deltas

    def _observation_deltas(self, event: CognitiveEvent) -> list[EmotionDelta]:
        observation = event.payload.get("obs") or event.payload.get("observation")
        novelty = 0.0
        entity = "unknown object"
        if hasattr(observation, "salience"):
            novelty = float(observation.salience.get("novelty", 0.0))
            entity = str(getattr(observation, "data", {}).get("entity", entity))
        elif isinstance(observation, dict):
            novelty = float(observation.get("salience", {}).get("novelty", observation.get("novelty", 0.0)))
            entity = str(observation.get("entity", entity))
        if novelty <= 0.7:
            return []
        return [
            EmotionDelta(
                "curiosity",
                0.1,
                event.episode_id,
                event.event,
                f"Unknown object discovered: {entity}.",
            ),
            EmotionDelta(
                "novelty",
                0.05,
                event.episode_id,
                event.event,
                f"Novel observation registered: {entity}.",
            ),
        ]

    def _learning_deltas(self, event: CognitiveEvent) -> list[EmotionDelta]:
        updates = event.payload.get("memory_updates") or []
        if not updates:
            return []
        return [
            EmotionDelta(
                "motivation",
                0.05,
                event.episode_id,
                event.event,
                f"Learning completed with {len(updates)} memory update(s).",
            )
        ]
