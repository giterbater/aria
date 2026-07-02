from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum


class PlanStepState(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    """A single step in a plan."""
    id: str = field(default_factory=lambda: str(__import__('uuid').uuid4()))
    description: str = ""
    action: str = ""  # what to do (tool name, delegation target, etc.)
    args: dict = field(default_factory=dict)
    state: PlanStepState = PlanStepState.PENDING
    depends_on: list[str] = field(default_factory=list)  # step IDs
    result: str = ""
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    completed_at: datetime.datetime | None = None

    @property
    def is_ready(self) -> bool:
        return self.state == PlanStepState.PENDING and not self.depends_on

    def can_run(self, completed_ids: set[str]) -> bool:
        return (
            self.state == PlanStepState.PENDING
            and all(dep in completed_ids for dep in self.depends_on)
        )


@dataclass
class Plan:
    """An ordered plan with steps, priorities, and progress tracking."""
    id: str = field(default_factory=lambda: str(__import__('uuid').uuid4()))
    objective: str = ""
    steps: list[PlanStep] = field(default_factory=list)
    priority: float = 1.0
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    updated_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    completed_at: datetime.datetime | None = None

    @property
    def progress(self) -> float:
        if not self.steps:
            return 0.0
        done = sum(1 for s in self.steps if s.state == PlanStepState.COMPLETED)
        return done / len(self.steps)

    @property
    def is_complete(self) -> bool:
        return all(s.state in (PlanStepState.COMPLETED, PlanStepState.SKIPPED) for s in self.steps)

    @property
    def next_step(self) -> PlanStep | None:
        completed = {s.id for s in self.steps if s.state == PlanStepState.COMPLETED}
        for step in self.steps:
            if step.can_run(completed):
                return step
        return None

    @property
    def failed_steps(self) -> list[PlanStep]:
        return [s for s in self.steps if s.state == PlanStepState.FAILED]
