"""Milestone 1 tests for the Cognitive OS environment contract."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

import aria_world
from aria_core.cognition.events import CognitiveEvent, Event
from aria_core.environment import (
    Action,
    ActionSchema,
    Environment,
    Observation,
    make,
    registered,
    validate_action,
)
from aria_world.config import SimulationConfig
from aria_world.world import WorldEngine
from event_bus import bus


def test_action_validation_accepts_published_schema() -> None:
    schema = ActionSchema(
        action_type="move",
        parameters={"dx": {"type": "number"}, "dy": {"type": "number"}},
        required_params=("dx", "dy"),
    )

    result = validate_action(
        Action(agent_id="aria", action_type="move", params={"dx": 1.0, "dy": -1.0}),
        [schema],
    )

    assert result.valid
    assert result.schema == schema


@pytest.mark.parametrize(
    ("action", "reason"),
    [
        (Action(agent_id="aria", action_type="jump"), "Unknown action_type"),
        (Action(agent_id="aria", action_type="move", params={"dx": 1.0}), "Missing required"),
        (Action(agent_id="aria", action_type="move", params={"dx": "far", "dy": 1}), "must be number"),
        (Action(agent_id="aria", action_type="move", params={"dx": 1, "dy": 1}, confidence=1.5), "confidence"),
    ],
)
def test_action_validation_rejects_invalid_actions(action: Action, reason: str) -> None:
    schema = ActionSchema(
        action_type="move",
        parameters={"dx": {"type": "number"}, "dy": {"type": "number"}},
        required_params=("dx", "dy"),
    )

    result = validate_action(action, [schema])

    assert not result.valid
    assert reason in result.reason


def test_cognitive_event_envelope_has_episode_and_timestamps() -> None:
    event = CognitiveEvent(
        agent_id="aria",
        event=Event.OBSERVATION,
        tick=3,
        payload={"observation": "symbolic"},
    )

    assert event.episode_id
    assert len(event.episode_id) == 12
    assert event.event == "cognition.observation"
    assert event.timestamp.tzinfo is not None
    assert event.t > 0


def test_world_engine_satisfies_environment_contract() -> None:
    env = WorldEngine(SimulationConfig(initial_agents=3, max_agents=5, max_days=5, seed=42))

    assert isinstance(env, Environment)

    obs = env.reset()
    assert isinstance(obs, Observation)
    assert obs.agent_id
    assert obs.tick == 0
    assert obs.timestamp <= datetime.now(timezone.utc)
    assert obs.data["alive_count"] == 3

    next_obs, reward, done, info = env.step(Action(agent_id=obs.agent_id, action_type="wait"))

    assert next_obs.tick == 1
    assert reward > 0
    assert not done
    assert info["accepted"] is True
    assert "result" in info
    assert env.get_state().tick == 1
    assert len(env.get_state().agents) == 3
    assert env.render()["tick"] == 1
    env.shutdown()


def test_small_city_environment_is_registered_and_created_by_name() -> None:
    assert "SmallCity-v0" in registered()

    env = make("SmallCity-v0", initial_agents=2, max_agents=4, max_days=3, seed=7)
    obs = env.reset()

    assert env.spec().name == "SmallCity-v0"
    assert obs.data["alive_count"] == 2
    assert {schema.action_type for schema in env.list_actions()} >= {"wait", "observe"}
    if hasattr(env, "shutdown"):
        env.shutdown()


def test_world_step_rejects_unknown_action_and_emits_event() -> None:
    env = WorldEngine(SimulationConfig(initial_agents=2, max_agents=4, max_days=3, seed=11))
    rejected: list[CognitiveEvent] = []

    def on_rejected(event: CognitiveEvent) -> None:
        rejected.append(event)

    bus.subscribe(Event.ACTION_REJECTED, on_rejected)
    try:
        obs = env.reset()
        next_obs, reward, done, info = env.step(Action(agent_id=obs.agent_id, action_type="fly"))
    finally:
        bus.unsubscribe(Event.ACTION_REJECTED, on_rejected)
        env.shutdown()

    assert next_obs.tick == 0
    assert reward == 0.0
    assert not done
    assert info["accepted"] is False
    assert rejected
    assert rejected[0].event == Event.ACTION_REJECTED
    assert rejected[0].payload["validated"] is False


def test_world_step_marks_aria_agent_in_snapshot() -> None:
    env = WorldEngine(SimulationConfig(initial_agents=2, max_agents=4, max_days=3, seed=13))
    obs = env.reset()
    agent_id = obs.data["agent_statuses"][0]["id"]

    _, _, _, info = env.step(
        Action(
            agent_id=agent_id,
            action_type="set_aria_agent",
            params={"agent_id": agent_id},
        )
    )
    snapshot = env.get_state()

    assert info["accepted"] is True
    assert any(agent.id == agent_id and agent.is_aria for agent in snapshot.agents)
    env.shutdown()


def test_legacy_world_tick_remains_backward_compatible() -> None:
    world = WorldEngine(SimulationConfig(initial_agents=3, max_agents=5, max_days=5, seed=99))
    world.initialize()

    result = world.tick()

    assert result["day"] == 1
    assert result["alive_count"] == 3
    assert "agent_statuses" in result
    assert "agent_positions" in result
    world.shutdown()
