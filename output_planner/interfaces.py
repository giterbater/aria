from __future__ import annotations
from typing import Protocol, runtime_checkable
from aria_core.interfaces import ARIDecision

@runtime_checkable
class OutputPlannerProtocol(Protocol):
    """Given an ARIA decision, produce a plan for the Language Cortex."""
    async def plan(self, decision: ARIDecision) -> dict:
        """
        Return a dictionary that the Language Cortex can consume.
        Expected keys (at minimum):
            - "prompt": str   # the text to feed to the Language Cortex
            - "speak": bool   # whether to actually speak the result
            - Optional: "priority", "urgency", "tone", "max_tokens", "temperature"
        """
        ...