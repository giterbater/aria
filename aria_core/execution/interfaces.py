# aria_core/execution/interfaces.py
"""
Action execution contract.

The executor turns an ARIA decision into a real-world side effect
(launch an app, set a reminder, …) and returns a structured outcome
the worker loop can use to drive outcome feedback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ActionResult:
    """What a tool returns to the worker loop after running."""
    success: bool
    message: str
    data: dict | None = None  # tool-specific structured return


@runtime_checkable
class ActionExecutor(Protocol):
    """Executes an ARIA decision in the world and returns the outcome."""

    def execute(self, *, tool_name: str, tool_args: dict) -> ActionResult:
        """Run the named tool. Must not raise; must return ActionResult."""
