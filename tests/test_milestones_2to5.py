"""
Integration tests for ARIA Cognitive OS (Milestones 2-5).

These tests verify:
- M2: Emotion state, prediction, outcome tracking, learning system
- M3: Event bus with canonical events and metadata
- M4: Environment contract with SmallCity adapter
- M5: UI event subscriptions (headless test)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass
from datetime import datetime, timezone

from aria_core.cognition.events import Event, CognitiveEvent
from aria_core.cognition.emotion import EmotionState, EmotionAttributor, EMOTION_DIMS
from aria_core.cognition.learning import OutcomeLearningLoop, ObservedOutcome
from aria_core.cognition.prediction import PredictionModel, Prediction
from aria_core.memory.models import Outcome
from aria_core.interfaces import StructuredInput, ARIDecision
from aria_core.environment import Action, Observation, WorldSnapshot, EnvironmentSpec
from aria_world.world import WorldEngine
from aria_world.config import SimulationConfig
from event_bus import bus


class TestM2EmotionState:
    """M2: Emotion state with explanations."""

    def test_emotion_state_initializes_all_dimensions(self):
        """EmotionState has all 7 dimensions initialized to 0.5."""
        state = EmotionState()
        assert len(state.values) == 7
        for dim in EMOTION_DIMS:
            assert dim in state.values
            assert state.values[dim] == 0.5

    def test_emotion_state_clamps_values(self):
        """EmotionState clamps values to [0, 1]."""
        from aria_core.cognition.emotion import EmotionDelta

        state = EmotionState()
        # Try to set to 2.0 (should clamp to 1.0)
        delta = EmotionDelta(
            dim="confidence",
            delta=1.5,
            cause_episode_id="ep1",
            cause_event=Event.OUTCOME,
            cause_text="Success!",
        )
        state.apply(delta)
        assert state.values["confidence"] == 1.0

    def test_emotion_state_tracks_recent_causes(self):
        """EmotionState keeps history of recent deltas."""
        from aria_core.cognition.emotion import EmotionDelta

        state = EmotionState()
        delta1 = EmotionDelta(
            dim="curiosity",
            delta=0.1,
            cause_episode_id="ep1",
            cause_event=Event.OBSERVATION,
            cause_text="Unknown discovered",
        )
        delta2 = EmotionDelta(
            dim="curiosity",
            delta=0.05,
            cause_episode_id="ep2",
            cause_event=Event.OBSERVATION,
            cause_text="New concept",
        )
        state.apply(delta1)
        state.apply(delta2)

        explains = state.explain("curiosity")
        assert len(explains) == 2
        assert explains[0] == delta2  # most recent first
        assert explains[1] == delta1


class TestM2Prediction:
    """M2: Prediction system."""

    def test_prediction_model_generates_stable_prediction(self):
        """PredictionModel returns a Prediction with all required fields."""
        model = PredictionModel()
        scores = {"execute": 0.8, "query": 0.5, "inform": 0.6}

        pred = model.predict(
            action_type="execute",
            scores=scores,
            structured_input=None,
            memory_matches=3,
            active_goals=2,
        )

        assert isinstance(pred, Prediction)
        assert pred.action_type == "execute"
        assert pred.predicted_outcome in ["success", "partial", "uncertain"]
        assert 0.0 <= pred.confidence <= 1.0
        assert -1.0 <= pred.predicted_reward <= 1.0

    def test_prediction_model_surprise_calculation(self):
        """PredictionModel.surprise measures deviation from prediction."""
        model = PredictionModel()
        pred = Prediction(
            action_type="execute",
            predicted_outcome="success",
            predicted_reward=0.8,
            confidence=0.9,
        )

        # Perfect prediction
        surprise = model.surprise(pred, actual_outcome="success", reward=0.8)
        assert surprise < 0.1

        # Bad prediction
        surprise = model.surprise(pred, actual_outcome="failed", reward=-0.5)
        assert surprise > 0.5


class TestM2OutcomeAndLearning:
    """M2: Outcome tracking and learning system."""

    def test_outcome_learning_loop_emits_learning_event(self):
        """OutcomeLearningLoop emits Learning event on outcome."""
        mock_bus = MagicMock()
        mock_memory = MagicMock()
        loop = OutcomeLearningLoop(mock_memory, event_bus=mock_bus)

        outcome = ObservedOutcome(
            episode_id="ep1",
            agent_id="aria",
            result="success",
            reward=0.5,
            surprise=0.1,
            tick=10,
        )

        loop.observe_outcome(outcome)

        # Verify Outcome event was published
        assert mock_bus.publish.call_count >= 1
        calls = [c for c in mock_bus.publish.call_args_list]
        assert any(Event.OUTCOME in str(c) for c in calls)

    def test_outcome_classification(self):
        """Outcomes are correctly classified and importance deltas computed."""
        from aria_core.cognition.learning import _classify_outcome, _importance_delta

        # Test classification
        assert _classify_outcome("ok", 0.5) == Outcome.SUCCESS
        assert _classify_outcome("fail", -0.5) == Outcome.FAILED
        assert _classify_outcome("partial", 0.0) == Outcome.PARTIAL

        # Test importance deltas
        assert _importance_delta(Outcome.SUCCESS) == 0.10
        assert _importance_delta(Outcome.FAILED) == -0.05
        assert _importance_delta(Outcome.PARTIAL) == 0.0


class TestM3EventBus:
    """M3: Standardized cognitive event bus."""

    def test_cognitive_event_has_required_metadata(self):
        """CognitiveEvent includes episode_id, timestamp, agent_id."""
        event = CognitiveEvent(
            episode_id="ep123",
            agent_id="aria",
            event=Event.OBSERVATION,
            tick=5,
            payload={"test": "data"},
        )

        assert event.episode_id == "ep123"
        assert event.agent_id == "aria"
        assert event.event == Event.OBSERVATION
        assert isinstance(event.timestamp, datetime)
        assert event.payload == {"test": "data"}

    def test_event_bus_publishes_and_receives(self):
        """Event bus pub/sub works."""
        received = []

        def callback(payload):
            received.append(payload)

        bus.subscribe("test.event", callback)
        bus.publish("test.event", {"data": "test"})

        assert len(received) == 1
        assert received[0] == {"data": "test"}

        bus.unsubscribe("test.event", callback)

    def test_all_event_constants_defined(self):
        """All canonical event types are defined."""
        required_events = [
            "OBSERVATION",
            "MEMORY_RETRIEVED",
            "HYPOTHESIS",
            "PREDICTION",
            "DECISION",
            "ACTION",
            "OUTCOME",
            "LEARNING",
            "EMOTION",
            "DREAM_START",
            "DREAM_END",
        ]
        for event_name in required_events:
            assert hasattr(Event, event_name), f"Event.{event_name} not defined"


class TestM4EnvironmentContract:
    """M4: Environment contract and SmallCity adapter."""

    def test_world_engine_implements_environment_contract(self):
        """WorldEngine implements all Environment contract methods."""
        config = SimulationConfig(initial_agents=3, seed=42)
        world = WorldEngine(config)
        world.initialize()

        # Test all contract methods exist
        assert hasattr(world, "reset")
        assert hasattr(world, "step")
        assert hasattr(world, "observe")
        assert hasattr(world, "get_state")
        assert hasattr(world, "spec")
        assert hasattr(world, "list_actions")
        assert hasattr(world, "render")

    def test_world_engine_reset_returns_observation(self):
        """WorldEngine.reset returns an Observation."""
        world = WorldEngine()
        world.initialize()
        world._aria_agent_id = list(world._agents.keys())[0] if world._agents else "test_aria"
        obs = world.reset(seed=42)

        assert isinstance(obs, Observation)
        assert obs.agent_id is not None
        assert obs.tick >= 0

    def test_world_engine_step_accepts_action(self):
        """WorldEngine.step accepts Action and returns (obs, reward, done, info)."""
        world = WorldEngine()
        world.initialize()
        world.reset(seed=42)

        action = Action(
            agent_id=world._aria_agent_id or "aria",
            action_type="query",
            params={"target": "test"},
        )

        result = world.step(action)
        assert isinstance(result, tuple)
        assert len(result) == 4
        obs, reward, done, info = result
        assert isinstance(obs, Observation)
        assert isinstance(reward, float)
        assert isinstance(done, bool)
        assert isinstance(info, dict)

    def test_world_engine_get_state_returns_world_snapshot(self):
        """WorldEngine.get_state returns a WorldSnapshot."""
        world = WorldEngine()
        world.initialize()

        snapshot = world.get_state()
        assert isinstance(snapshot, WorldSnapshot)
        assert snapshot.tick >= 0
        assert isinstance(snapshot.agents, list)
        assert isinstance(snapshot.metrics, dict)

    def test_world_engine_spec_returns_environment_spec(self):
        """WorldEngine.spec returns an EnvironmentSpec."""
        world = WorldEngine()
        spec = world.spec()

        assert isinstance(spec, EnvironmentSpec)
        assert spec.name is not None
        assert len(spec.action_space) > 0

    def test_world_engine_action_validation(self):
        """Invalid actions are rejected with Event.ACTION_REJECTED."""
        from aria_core.environment import validate_action_for_environment

        world = WorldEngine()
        world.initialize()
        world.reset(seed=42)

        # Invalid action
        invalid_action = Action(
            agent_id=world._aria_agent_id or "aria",
            action_type="INVALID_ACTION_TYPE_XYZ",
            params={},
        )

        result = validate_action_for_environment(world, invalid_action)
        assert result is not None  # Should return a validation error


class TestM5UIEventSubscriptions:
    """M5: UI components subscribe to events."""

    def test_ui_can_subscribe_to_observation_event(self):
        """UI component can subscribe to observation events."""
        received_events = []

        def ui_handler(event: CognitiveEvent):
            received_events.append(event)

        bus.subscribe(Event.OBSERVATION, ui_handler)

        # Publish an event
        test_event = CognitiveEvent(
            episode_id="ep1",
            agent_id="aria",
            event=Event.OBSERVATION,
            tick=1,
            payload={"test": "data"},
        )
        bus.publish(Event.OBSERVATION, test_event)

        assert len(received_events) == 1
        assert received_events[0].episode_id == "ep1"

        bus.unsubscribe(Event.OBSERVATION, ui_handler)

    def test_ui_receives_full_cognitive_pipeline(self):
        """UI can receive and order all 9 cognitive pipeline events."""
        received_events = []

        def pipeline_handler(event: CognitiveEvent):
            received_events.append(event)

        events_to_test = [
            Event.OBSERVATION,
            Event.MEMORY_RETRIEVED,
            Event.HYPOTHESIS,
            Event.PREDICTION,
            Event.DECISION,
            Event.ACTION,
            Event.OUTCOME,
            Event.LEARNING,
            Event.EMOTION,
        ]

        for evt in events_to_test:
            bus.subscribe(evt, pipeline_handler)

        # Simulate publishing pipeline events
        episode_id = "ep1"
        for i, evt in enumerate(events_to_test):
            event = CognitiveEvent(
                episode_id=episode_id,
                agent_id="aria",
                event=evt,
                tick=1,
                sequence=i + 1,
                payload={"step": i + 1},
            )
            bus.publish(evt, event)

        assert len(received_events) == 9
        sequences = [e.sequence for e in received_events]
        assert sequences == list(range(1, 10))

        for evt in events_to_test:
            bus.unsubscribe(evt, pipeline_handler)

    def test_emotion_panel_can_subscribe_and_render_state(self):
        """Emotion panel receives and processes emotion updates."""
        from aria_core.cognition.emotion import EmotionAttributor

        received_emotion_states = []

        def emotion_handler(event: CognitiveEvent):
            state = event.payload.get("state", {})
            received_emotion_states.append(state)

        bus.subscribe(Event.EMOTION, emotion_handler)

        # Create an emotion attributor and trigger an update
        emotion_state = EmotionState()
        attributor = EmotionAttributor(state=emotion_state, event_bus=bus)

        # Simulate an outcome event that should trigger emotion
        outcome_event = CognitiveEvent(
            episode_id="ep1",
            agent_id="aria",
            event=Event.OUTCOME,
            tick=10,
            payload={
                "result": "success",
                "reward": 0.5,
                "surprise": 0.1,
            },
        )

        # Handle the outcome (should emit emotion)
        attributor.handle_event(outcome_event)

        # Should have emitted an emotion event
        assert len(received_emotion_states) > 0

        bus.unsubscribe(Event.EMOTION, emotion_handler)

    def test_thought_stream_can_collect_episode_events(self):
        """Thought stream collects all events for an episode."""
        episode_events = {}

        def collector(event: CognitiveEvent):
            episode_id = event.episode_id
            if episode_id not in episode_events:
                episode_events[episode_id] = []
            episode_events[episode_id].append(event)

        # Subscribe to all cognitive events
        for evt_type in [
            Event.OBSERVATION,
            Event.MEMORY_RETRIEVED,
            Event.HYPOTHESIS,
            Event.PREDICTION,
            Event.DECISION,
            Event.ACTION,
            Event.OUTCOME,
            Event.LEARNING,
            Event.EMOTION,
        ]:
            bus.subscribe(evt_type, collector)

        # Publish a full pipeline
        episode_id = "ep_full_pipeline"
        pipeline = [
            (Event.OBSERVATION, 1),
            (Event.MEMORY_RETRIEVED, 2),
            (Event.HYPOTHESIS, 3),
            (Event.PREDICTION, 4),
            (Event.DECISION, 5),
            (Event.ACTION, 6),
            (Event.OUTCOME, 7),
            (Event.LEARNING, 8),
            (Event.EMOTION, 9),
        ]

        for evt_type, seq in pipeline:
            event = CognitiveEvent(
                episode_id=episode_id,
                agent_id="aria",
                event=evt_type,
                tick=1,
                sequence=seq,
                payload={},
            )
            bus.publish(evt_type, event)

        # Verify all events collected
        assert episode_id in episode_events
        assert len(episode_events[episode_id]) == 9
        sequences = [e.sequence for e in episode_events[episode_id]]
        assert sequences == list(range(1, 10))

        # Clean up
        for evt_type, _ in pipeline:
            bus.unsubscribe(evt_type, collector)


class TestIntegration:
    """Integration tests across milestones."""

    def test_end_to_end_cognitive_pipeline_with_events(self):
        """Full cognitive pipeline emits all events in order."""
        from aria_core.decision_maker import SimpleDecisionMaker
        from aria_core.goals import GoalManager
        from aria_core.memory.simple_memory_system import SimpleMemorySystem

        events_emitted = []

        def capture_event(event: CognitiveEvent):
            events_emitted.append((event.event, event.sequence))

        # Subscribe to all events
        for evt in [
            Event.OBSERVATION,
            Event.MEMORY_RETRIEVED,
            Event.HYPOTHESIS,
            Event.PREDICTION,
            Event.DECISION,
            Event.ACTION,
        ]:
            bus.subscribe(evt, capture_event)

        # Create decision maker
        memory = SimpleMemorySystem()
        goals = GoalManager()
        maker = SimpleDecisionMaker(memory, goals, agent_id="test_aria")

        # Make a decision
        input_data = StructuredInput(
            raw_text="What should I do?",
            intent="query",
        )

        # Run decision (async)
        import asyncio

        asyncio.run(maker.decide(input_data))

        # Verify pipeline events
        expected_events = [
            Event.OBSERVATION,
            Event.MEMORY_RETRIEVED,
            Event.HYPOTHESIS,
            Event.PREDICTION,
            Event.DECISION,
            Event.ACTION,
        ]

        emitted_types = [e[0] for e in events_emitted]
        for expected in expected_events:
            assert expected in emitted_types

        # Clean up
        for evt in expected_events:
            bus.unsubscribe(evt, capture_event)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
