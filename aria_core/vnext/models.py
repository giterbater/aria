# aria_core/vnext/models.py
"""
Typed models for ARIA vNext.

All data flows through these typed models.
No dictionaries at module boundaries.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Experience & Learning
# ---------------------------------------------------------------------------

class ExperienceType(str, Enum):
    """Types of experiences ARIA can have."""
    INTERACTION = "interaction"
    TASK = "task"
    OBSERVATION = "observation"
    ERROR = "error"
    SUCCESS = "success"
    FAILURE = "failure"
    DISCOVERY = "discovery"
    SOCIAL = "social"


class LearningAction(str, Enum):
    """Actions the LearningManager can produce."""
    IGNORE = "ignore"
    STORE_EPISODIC = "store_episodic"
    STRENGTHEN_SEMANTIC = "strengthen_semantic"
    UPDATE_IDENTITY = "update_identity"
    UPDATE_VALUES = "update_values"
    UPDATE_EMOTIONAL_STATE = "update_emotional_state"
    TRIGGER_RETRAINING = "trigger_retraining"
    SCHEDULE_CONSOLIDATION = "schedule_consolidation"
    CONSOLIDATE_NOW = "consolidate_now"


@dataclass
class Experience:
    """A single experience to be evaluated."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    experience_type: ExperienceType = ExperienceType.INTERACTION
    
    # Content
    action: str = ""
    result: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    
    # Outcome
    success: bool = False
    reward: float = 0.0  # -1.0 to 1.0
    
    # Emotional content
    emotional_valence: float = 0.0  # -1.0 (negative) to 1.0 (positive)
    emotional_intensity: float = 0.0  # 0.0 to 1.0
    
    # Metadata
    source: str = ""
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImportanceScore:
    """Score indicating how important an experience is."""
    score: float = 0.0  # 0.0 to 1.0
    reasons: list[str] = field(default_factory=list)
    confidence: float = 0.0  # 0.0 to 1.0
    
    @property
    def is_important(self) -> bool:
        """Check if this experience is important enough to store."""
        return self.score >= 0.5
    
    @property
    def is_critical(self) -> bool:
        """Check if this experience is critical."""
        return self.score >= 0.8


@dataclass
class LearningActionPlan:
    """A set of actions to take for an experience."""
    experience_id: str = ""
    importance: ImportanceScore = field(default_factory=ImportanceScore)
    actions: list[LearningAction] = field(default_factory=list)
    reasoning: str = ""
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)


# ---------------------------------------------------------------------------
# Emotional State
# ---------------------------------------------------------------------------

class EmotionType(str, Enum):
    """Types of adaptive emotions."""
    CURIOSITY = "curiosity"
    CONFIDENCE = "confidence"
    FRUSTRATION = "frustration"
    MOTIVATION = "motivation"
    FATIGUE = "fatigue"
    ATTACHMENT = "attachment"
    STRESS = "stress"


@dataclass
class EmotionalState:
    """Current emotional state."""
    curiosity: float = 0.5  # 0.0 to 1.0
    confidence: float = 0.7  # 0.0 to 1.0
    frustration: float = 0.0  # 0.0 to 1.0
    motivation: float = 0.7  # 0.0 to 1.0
    fatigue: float = 0.0  # 0.0 to 1.0
    attachment: float = 0.3  # 0.0 to 1.0
    stress: float = 0.0  # 0.0 to 1.0
    
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    
    def get(self, emotion: EmotionType) -> float:
        """Get value for an emotion type."""
        return getattr(self, emotion.value, 0.5)
    
    def set(self, emotion: EmotionType, value: float) -> None:
        """Set value for an emotion type (clamped to 0-1)."""
        setattr(self, emotion.value, max(0.0, min(1.0, value)))
    
    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary."""
        return {
            "curiosity": self.curiosity,
            "confidence": self.confidence,
            "frustration": self.frustration,
            "motivation": self.motivation,
            "fatigue": self.fatigue,
            "attachment": self.attachment,
            "stress": self.stress,
        }


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------

class MemoryType(str, Enum):
    """Types of memory."""
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    IDENTITY = "identity"
    VALUE = "value"
    PERCEPTION = "perception"


@dataclass
class MemoryEntry:
    """A single memory entry."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    memory_type: MemoryType = MemoryType.EPISODIC
    
    # Content
    content: Any = None
    embedding: list[float] = field(default_factory=list)
    
    # Metadata
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    importance: float = 0.5
    confidence: float = 0.5
    access_count: int = 0
    last_accessed: Optional[datetime.datetime] = None
    
    # Associations
    source_experience_id: Optional[str] = None
    associated_ids: list[str] = field(default_factory=list)
    
    # Decay
    decay_rate: float = 0.01


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

@dataclass
class ContextState:
    """Fused context from multiple sources."""
    location: str = "unknown"
    familiarity: float = 0.0
    motion: str = "stationary"
    confidence: float = 0.0
    evidence: dict[str, Any] = field(default_factory=dict)
    
    # Source tracking
    sources: list[str] = field(default_factory=list)
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "location": self.location,
            "familiarity": self.familiarity,
            "motion": self.motion,
            "confidence": self.confidence,
            "sources": self.sources,
        }
