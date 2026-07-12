"""Typed boundary between ARIA and any environment.

ARIA receives Observations, emits Actions, and treats the fields inside
Observation.data and Action.params as environment-owned vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Observation:
    """What ARIA sees at this tick."""

    agent_id: str
    tick: int
    timestamp: datetime
    data: dict[str, Any]
    modality: str = "symbolic"
    salience: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Action:
    """What ARIA wants to do."""

    agent_id: str
    action_type: str
    params: dict[str, Any] = field(default_factory=dict)
    rationale: str | None = None
    confidence: float = 1.0


@dataclass(frozen=True)
class ActionSchema:
    """Typed action catalog entry published by an environment."""

    action_type: str
    description: str = ""
    parameters: dict[str, dict[str, Any]] = field(default_factory=dict)
    required_params: tuple[str, ...] = ()
    examples: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class AgentSnapshot:
    id: str
    name: str
    occupation: str
    position: tuple[float, float]
    velocity: tuple[float, float] = (0.0, 0.0)
    mood: dict[str, float] = field(default_factory=dict)
    current_task: str = ""
    inventory: dict[str, float] = field(default_factory=dict)
    alive: bool = True
    is_aria: bool = False
    thought: str = ""


@dataclass(frozen=True)
class BuildingSnapshot:
    id: str
    kind: str
    position: tuple[float, float]
    size: tuple[float, float] = (1.0, 1.0)
    label: str = ""
    occupants: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RoadSegment:
    id: str
    start: tuple[float, float]
    end: tuple[float, float]
    kind: str = "road"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorldEvent:
    id: str
    tick: int
    event_type: str
    description: str
    severity: float = 0.0
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorldSnapshot:
    """Everything the UI needs to render a world tick."""

    tick: int
    time_of_day: float
    day: int
    season: str
    weather: str
    agents: list[AgentSnapshot]
    resources: dict[str, float]
    buildings: list[BuildingSnapshot]
    roads: list[RoadSegment]
    events: list[WorldEvent]
    metrics: dict[str, float]


@dataclass(frozen=True)
class EnvironmentSpec:
    name: str
    version: str
    observation_space: dict[str, Any]
    action_space: list[ActionSchema]
    max_ticks: int
    population_range: tuple[int, int]
    description: str


@runtime_checkable
class Environment(Protocol):
    """The smallest interface an environment must satisfy."""

    def reset(self, seed: int | None = None) -> Observation: ...

    def step(self, action: Action) -> tuple[Observation, float, bool, dict]: ...

    def observe(self, agent_id: str | None = None) -> Observation: ...

    def get_state(self) -> WorldSnapshot: ...

    def list_actions(self) -> list[ActionSchema]: ...

    def render(self, mode: str = "ui") -> Any: ...

    def spec(self) -> EnvironmentSpec: ...
