"""Canonical event names and envelopes for the cognitive OS."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class Event:
    OBSERVATION = "cognition.observation"
    MEMORY_RETRIEVED = "cognition.memory_retrieved"
    HYPOTHESIS = "cognition.hypothesis"
    PREDICTION = "cognition.prediction"
    DECISION = "cognition.decision"
    ACTION = "cognition.action"
    ACTION_REJECTED = "cognition.action_rejected"
    OUTCOME = "cognition.outcome"
    LEARNING = "cognition.learning"
    EMOTION = "cognition.emotion"
    MEMORY_STORED = "cognition.memory_stored"
    DREAM_START = "cognition.dream.start"
    DREAM_REPLAY = "cognition.dream.replay"
    DREAM_CONSOLIDATE = "cognition.dream.consolidate"
    DREAM_EXTRACT = "cognition.dream.extract"
    DREAM_FORGET = "cognition.dream.forget"
    DREAM_END = "cognition.dream.end"


@dataclass(frozen=True)
class CognitiveEvent:
    episode_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_id: str = ""
    event: str = ""
    tick: int = 0
    sequence: int = 0
    t: float = field(default_factory=time.time)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = field(default_factory=dict)
