from __future__ import annotations
from dataclasses import dataclass, field
import datetime
from typing import List, Optional, Literal

@dataclass
class Entity:
    text: str
    label: str                     # e.g., "APP", "PERSON", "TIME"
    confidence: float = 1.0

@dataclass
class StructuredInput:
    """Output of the Input Interpreter."""
    raw_text: str
    intent: str                    # e.g., "open_application", "question", "statement"
    entities: List[Entity] = field(default_factory=list)
    facts: List[str] = field(default_factory=list)   # explicit statements user made
    questions: List[str] = field(default_factory=list)
    emotional_cue: Optional[str] = None              # e.g., "frustrated", "excited"
    confidence: float = 1.0                          # overall confidence of interpretation
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    importance: float = 0.5

@dataclass
class ARIDecision:
    """Decision produced by ARIA Core after reasoning."""
    action_type: str                     # e.g., "inform", "warn", "execute", "query"
    payload: dict = field(default_factory=dict)   # domain‑specific data
    priority: Literal["low", "normal", "high"] = "normal"
    urgency: Literal["low", "normal", "high"] = "normal"
    tone: Literal["neutral", "friendly", "formal", "empathetic", "calm"] = "neutral"
    speak: bool = True                   # should ARIA speak this decision?
