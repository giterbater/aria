"""Environment contract for pluggable ARIA worlds."""

from .contract import (
    Action,
    ActionSchema,
    AgentSnapshot,
    BuildingSnapshot,
    Environment,
    EnvironmentSpec,
    Observation,
    RoadSegment,
    WorldEvent,
    WorldSnapshot,
)
from .registry import make, register, registered
from .validation import ActionValidationError, ValidationResult, validate_action, validate_action_for_environment

__all__ = [
    "Action",
    "ActionSchema",
    "ActionValidationError",
    "AgentSnapshot",
    "BuildingSnapshot",
    "Environment",
    "EnvironmentSpec",
    "Observation",
    "RoadSegment",
    "ValidationResult",
    "WorldEvent",
    "WorldSnapshot",
    "make",
    "register",
    "registered",
    "validate_action",
    "validate_action_for_environment",
]
