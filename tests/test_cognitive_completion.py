"""Milestone 2 tests for cognitive completion."""

from __future__ import annotations

import asyncio

from aria_core.cognition import (
    EmotionAttributor,
    EmotionDelta,
    EmotionState,
    Event,
    ObservedOutcome,
    OutcomeLearningLoop,
    PredictionModel,
)
from aria_core.cognition.events import CognitiveEvent
from aria_core.decision_maker import SimpleDecisionMaker
from aria_core.goals import GoalManager
from aria_core.interfaces import StructuredInput
from aria_core.memory.models import EpisodicItem, Outcome
from aria_core.memory.simple_memory_system import SimpleMemorySystem
from event_bus import bus


def _run(coro):
    return asyncio.run(coro)


def test_decision_maker_emits_ordered_episode_events() -> None:
    memory = SimpleMemorySystem()
    maker = SimpleDecisionMaker(memory=memory, goals=GoalManager(), agent_id="agent-1")
    received: list[CognitiveEvent] = []
    event_names = [
        Event.OBSERVATION,
        Event.MEMORY_RETRIEVED,
        Event.HYPOTHESIS,
        Event.PREDICTION,
        Event.DECISION,
        Event.ACTION,
    ]

    for event_name in event_names:
        bus.subscribe(event_name, received.append)
    try:
        decision = _run(maker.decide(StructuredInput(raw_text="What is ARIA?", intent="question")))
    finally:
        for event_name in event_names:
            bus.unsubscribe(event_name, received.append)

    assert decision.action_type == "query"
    assert [event.event for event in received] == event_names
    assert [event.sequence for event in received] == [1, 2, 3, 4, 5, 6]
    assert len({event.episode_id for event in received}) == 1
    assert maker.last_episode_id == received[0].episode_id

    episode = memory.get_episodic(limit=1)[0]
    assert episode.id == maker.last_episode_id
    assert episode.metadata["episode_id"] == maker.last_episode_id
    assert "prediction" in episode.metadata


def test_simple_memory_record_outcome_updates_episode() -> None:
    memory = SimpleMemorySystem()
    episode = EpisodicItem(id="ep-1", importance=0.5, outcome=None)
    memory.store_episodic(episode)

    memory.record_outcome("ep-1", Outcome.SUCCESS, notes="worked")

    loaded = memory.get_episodic(limit=1)[0]
    assert loaded.outcome == "success"
    assert loaded.notes == "worked"
    assert loaded.importance == 0.6


def test_outcome_learning_loop_emits_learning_and_updates_memory() -> None:
    memory = SimpleMemorySystem()
    memory.store_episodic(EpisodicItem(id="ep-2", importance=0.5))
    loop = OutcomeLearningLoop(memory)
    learning_events: list[CognitiveEvent] = []
    bus.subscribe(Event.LEARNING, learning_events.append)
    try:
        event = loop.observe_outcome(
            ObservedOutcome(
                episode_id="ep-2",
                agent_id="agent-1",
                result="failed",
                reward=-0.4,
                surprise=0.8,
                notes="tool failed",
            )
        )
    finally:
        bus.unsubscribe(Event.LEARNING, learning_events.append)

    loaded = memory.get_episodic(limit=1)[0]
    assert event.event == Event.LEARNING
    assert learning_events == [event]
    assert loaded.outcome == "failed"
    assert loaded.notes == "tool failed"
    assert loaded.importance == 0.45
    assert event.payload["memory_updates"][0]["item_id"] == "ep-2"


def test_emotion_state_explains_causes() -> None:
    state = EmotionState()
    delta = EmotionDelta(
        dim="confidence",
        delta=-0.2,
        cause_episode_id="ep-3",
        cause_event=Event.OUTCOME,
        cause_text="Prediction failed.",
    )

    state.apply(delta)

    assert state.values["confidence"] == 0.3
    assert state.explain("confidence") == [delta]


def test_emotion_attributor_emits_explained_emotion_update() -> None:
    attributor = EmotionAttributor()
    emotion_events: list[CognitiveEvent] = []
    bus.subscribe(Event.EMOTION, emotion_events.append)
    try:
        event = attributor.handle_event(
            CognitiveEvent(
                episode_id="ep-4",
                agent_id="agent-1",
                event=Event.OUTCOME,
                sequence=7,
                payload={"result": "failed", "reward": -0.5, "surprise": 0.9},
            )
        )
    finally:
        bus.unsubscribe(Event.EMOTION, emotion_events.append)

    assert event is not None
    assert emotion_events == [event]
    assert event.event == Event.EMOTION
    assert event.sequence == 9
    assert event.payload["delta"]["confidence"] < 0
    assert "Prediction failed" in event.payload["cause"]["confidence"]


def test_prediction_model_returns_stable_payload_and_surprise() -> None:
    model = PredictionModel()
    prediction = model.predict(
        action_type="query",
        scores={"query": 2.0, "inform": 0.5},
        structured_input=StructuredInput(raw_text="What is ARIA?", intent="question"),
        memory_matches=2,
        active_goals=1,
    )

    payload = prediction.to_payload()

    assert payload["model_id"] == "heuristic-v0"
    assert payload["action_type"] == "query"
    assert payload["predicted_outcome"] in {"success", "partial", "uncertain"}
    assert model.surprise(prediction, actual_outcome="failed", reward=-0.4) > 0.5
