from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ToolResult:
    """Result from a CTO tool execution. Never raised as exception."""
    success: bool
    output: str
    metadata: dict = field(default_factory=dict)


@runtime_checkable
class ToolProtocol(Protocol):
    """Contract for all CTO tools."""

    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def destructive(self) -> bool: ...

    def execute(self, **kwargs) -> ToolResult: ...
