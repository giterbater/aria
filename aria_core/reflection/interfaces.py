from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum


class ReflectionType(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    IMPROVEMENT = "improvement"
    LEARNING = "learning"
    OBSERVATION = "observation"


@dataclass
class Lesson:
    """A single insight extracted from experience."""
    id: str = field(default_factory=lambda: str(__import__('uuid').uuid4()))
    text: str = ""
    reflection_type: ReflectionType = ReflectionType.LEARNING
    source: str = ""  # what triggered this lesson
    confidence: float = 1.0
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    tags: list[str] = field(default_factory=list)


@dataclass
class Reflection:
    """A reflection on a completed action or outcome."""
    id: str = field(default_factory=lambda: str(__import__('uuid').uuid4()))
    reflection_type: ReflectionType = ReflectionType.OBSERVATION
    summary: str = ""
    what_worked: list[str] = field(default_factory=list)
    what_failed: list[str] = field(default_factory=list)
    what_to_improve: list[str] = field(default_factory=list)
    lessons: list[Lesson] = field(default_factory=list)
    context: dict = field(default_factory=dict)
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)


@dataclass
class SkillOutcome:
    """Outcome from a skill execution for reflection."""
    skill_name: str
    action: str
    success: bool
    duration_ms: float = 0.0
    output: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class ReflectionSummary:
    """Aggregated reflection data for decision-making."""
    total_reflections: int = 0
    successes: int = 0
    failures: int = 0
    improvements: int = 0
    skill_success_rates: dict[str, float] = field(default_factory=dict)
    top_patterns: list[tuple[str, int]] = field(default_factory=list)
    recent_insights: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
