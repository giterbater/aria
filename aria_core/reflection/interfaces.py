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
