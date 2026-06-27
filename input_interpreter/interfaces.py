from __future__ import annotations
from typing import Protocol, runtime_checkable
from aria_core.interfaces import StructuredInput

@runtime_checkable
class InputInterpreterProtocol(Protocol):
    """Turn raw user text into a StructuredInput."""
    async def interpret(self, raw_text: str) -> StructuredInput:
        """Interpret `raw_text` and return structured semantics."""
        ...