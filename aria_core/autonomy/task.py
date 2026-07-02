from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING = "waiting"  # waiting for external input


@dataclass
class TaskResult:
    """Result of a task execution."""
    success: bool
    output: Any = None
    error: str = ""
    duration_ms: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class Task:
    """A long-running task with checkpoint support."""
    id: str = field(default_factory=lambda: str(__import__('uuid').uuid4()))
    name: str = ""
    description: str = ""
    state: TaskState = TaskState.PENDING
    priority: float = 1.0

    # Execution
    steps: list[dict] = field(default_factory=list)  # ordered steps to execute
    current_step: int = 0
    result: TaskResult | None = None

    # Metadata
    metadata: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)  # task IDs

    # Timing
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    started_at: datetime.datetime | None = None
    completed_at: datetime.datetime | None = None
    updated_at: datetime.datetime = field(default_factory=datetime.datetime.now)

    # Error handling
    retry_count: int = 0
    max_retries: int = 3
    last_error: str = ""

    @property
    def progress(self) -> float:
        if not self.steps:
            return 1.0 if self.state == TaskState.COMPLETED else 0.0
        if self.state == TaskState.COMPLETED:
            return 1.0
        return self.current_step / len(self.steps)

    @property
    def is_terminal(self) -> bool:
        return self.state in (
            TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED,
        )

    @property
    def can_retry(self) -> bool:
        return self.state == TaskState.FAILED and self.retry_count < self.max_retries

    @property
    def elapsed_seconds(self) -> float | None:
        if self.started_at is None:
            return None
        end = self.completed_at or datetime.datetime.now()
        return (end - self.started_at).total_seconds()
