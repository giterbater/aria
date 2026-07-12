from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class SpecialistRequest:
    """A task to delegate to a specialist subprocess."""
    specialist_name: str
    task_description: str
    context_files: list[str] = field(default_factory=list)
    file_contents: dict[str, str] = field(default_factory=dict)
    error_output: str = ""
    constraints: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SpecialistResponse:
    """Result from a specialist subprocess."""
    specialist_name: str
    status: str  # "success" | "failed" | "partial"
    output: str
    summary: str = ""
    files_modified: list[str] = field(default_factory=list)
    diff: str = ""
    reasoning: str = ""


@runtime_checkable
class SpecialistSpawner(Protocol):
    """Protocol for spawning specialist subprocess agents."""

    def spawn(self, request: SpecialistRequest) -> SpecialistResponse: ...
