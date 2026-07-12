"""Action validation for the environment contract."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable

from .contract import Action, ActionSchema, Environment

logger = logging.getLogger("aria.environment.validation")


class ActionValidationError(ValueError):
    """Raised when an Action does not satisfy an environment's action catalog."""


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    reason: str = ""
    schema: ActionSchema | None = None


_JSON_TYPE_MAP: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
    "object": (dict,),
    "array": (list,),
    "null": (type(None),),
}


def validate_action(
    action: Action,
    action_space: Iterable[ActionSchema],
    *,
    raise_on_error: bool = False,
) -> ValidationResult:
    """Validate an Action against a published action space."""

    schemas = {schema.action_type: schema for schema in action_space}
    schema = schemas.get(action.action_type)
    if schema is None:
        return _invalid(
            f"Unknown action_type '{action.action_type}'",
            raise_on_error,
        )

    if not 0.0 <= action.confidence <= 1.0:
        return _invalid(
            f"Action confidence must be between 0.0 and 1.0, got {action.confidence}",
            raise_on_error,
            schema,
        )

    missing = [name for name in schema.required_params if name not in action.params]
    if missing:
        return _invalid(
            f"Missing required params: {', '.join(missing)}",
            raise_on_error,
            schema,
        )

    for name, param_schema in schema.parameters.items():
        if name not in action.params:
            continue
        allowed_type = param_schema.get("type")
        if allowed_type and not _matches_json_type(action.params[name], allowed_type):
            return _invalid(
                f"Param '{name}' must be {allowed_type}",
                raise_on_error,
                schema,
            )

    return ValidationResult(valid=True, schema=schema)


def validate_action_for_environment(
    environment: Environment,
    action: Action,
    *,
    raise_on_error: bool = False,
    publish_rejection: bool = True,
) -> ValidationResult:
    """Validate an Action against environment.list_actions()."""

    result = validate_action(action, environment.list_actions(), raise_on_error=raise_on_error)
    if not result.valid and publish_rejection:
        _publish_action_rejected(environment, action, result.reason)
    return result


def _invalid(
    reason: str,
    raise_on_error: bool,
    schema: ActionSchema | None = None,
) -> ValidationResult:
    if raise_on_error:
        raise ActionValidationError(reason)
    return ValidationResult(valid=False, reason=reason, schema=schema)


def _matches_json_type(value: Any, allowed_type: Any) -> bool:
    allowed = allowed_type if isinstance(allowed_type, list) else [allowed_type]
    for type_name in allowed:
        python_types = _JSON_TYPE_MAP.get(str(type_name))
        if not python_types:
            continue
        if str(type_name) in {"integer", "number"} and isinstance(value, bool):
            continue
        if isinstance(value, python_types):
            return True
    return False


def _publish_action_rejected(environment: Environment, action: Action, reason: str) -> None:
    try:
        from aria_core.cognition.events import CognitiveEvent, Event
        from event_bus import bus

        try:
            env_name = environment.spec().name
            tick = environment.get_state().tick
        except Exception:
            env_name = ""
            tick = 0

        bus.publish(
            Event.ACTION_REJECTED,
            CognitiveEvent(
                agent_id=action.agent_id,
                event=Event.ACTION_REJECTED,
                tick=tick,
                payload={
                    "environment": env_name,
                    "action": action,
                    "reason": reason,
                    "validated": False,
                },
            ),
        )
    except Exception as exc:
        logger.warning("Failed to publish ActionRejected event: %s", exc, exc_info=True)
