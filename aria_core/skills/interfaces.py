from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class SkillResult:
    """Structured result from a skill execution."""
    success: bool
    output: Any = None
    duration_ms: float = 0.0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @classmethod
    def ok(cls, output: Any = None, **meta) -> SkillResult:
        return cls(success=True, output=output, metadata=meta)

    @classmethod
    def fail(cls, error: str, **meta) -> SkillResult:
        return cls(success=False, errors=[error], metadata=meta)


@dataclass
class SkillMeta:
    """Metadata describing a skill's capabilities and requirements."""
    name: str
    description: str
    version: str = "1.0.0"
    category: str = "general"
    required_permissions: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)  # other skill names
    tags: list[str] = field(default_factory=list)
    timeout_seconds: float = 30.0
    destructive: bool = False


@runtime_checkable
class Skill(Protocol):
    """Interface every skill must implement."""

    @property
    def meta(self) -> SkillMeta: ...

    def execute(self, **kwargs) -> SkillResult: ...

    def validate(self, **kwargs) -> bool:
        """Check if the skill can execute with given args."""
        ...

    def rollback(self, context: dict) -> SkillResult:
        """Undo changes if applicable."""
        ...
