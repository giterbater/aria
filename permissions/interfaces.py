from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable


class PermissionTier(Enum):
    AUTO = "auto"
    ASK = "ask"
    BLOCK = "block"


@runtime_checkable
class PermissionPolicy(Protocol):
    """Determines the permission tier for a tool invocation."""

    def tier_for(self, tool_name: str, args: dict) -> PermissionTier: ...
    def is_allowed(self, tool_name: str, args: dict) -> bool: ...
    def requires_approval(self, tool_name: str, args: dict) -> bool: ...
