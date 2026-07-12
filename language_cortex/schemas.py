from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any

from aria_core.interfaces import Entity, StructuredInput


@dataclass
class IntentPrediction:
    intent: str
    confidence: float
    alternative_intents: list[tuple[str, float]] = field(default_factory=list)
    ambiguities: list[str] = field(default_factory=list)
    requires_clarification: bool = False


@dataclass
class ReferenceResolution:
    expression: str
    resolved_text: str | None = None
    source: str = "unresolved"
    confidence: float = 0.0


@dataclass
class ResponsePlan:
    purpose: str
    tone: str = "neutral"
    required_information: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    citations_needed: bool = False
    response_structure: list[str] = field(default_factory=list)
    follow_up_questions: list[str] = field(default_factory=list)

    @property
    def requires_clarification(self) -> bool:
        return bool(self.missing_information or self.follow_up_questions)

    def to_prompt_section(self) -> str:
        lines = [
            "ResponsePlan:",
            f"- purpose: {self.purpose}",
            f"- tone: {self.tone}",
            f"- citations_needed: {self.citations_needed}",
        ]
        if self.required_information:
            lines.append("- required_information: " + "; ".join(self.required_information))
        if self.missing_information:
            lines.append("- missing_information: " + "; ".join(self.missing_information))
        if self.response_structure:
            lines.append("- response_structure: " + " -> ".join(self.response_structure))
        if self.follow_up_questions:
            lines.append("- follow_up_questions: " + "; ".join(self.follow_up_questions))
        return "\n".join(lines)


@dataclass
class ConsistencyReport:
    contradictions: list[str] = field(default_factory=list)
    unsupported_claims: list[str] = field(default_factory=list)
    inconsistent_terminology: list[str] = field(default_factory=list)
    missing_references: list[str] = field(default_factory=list)
    unresolved_pronouns: list[str] = field(default_factory=list)
    incomplete_answers: list[str] = field(default_factory=list)

    @property
    def issues(self) -> list[str]:
        return (
            self.contradictions
            + self.unsupported_claims
            + self.inconsistent_terminology
            + self.missing_references
            + self.unresolved_pronouns
            + self.incomplete_answers
        )

    @property
    def passed(self) -> bool:
        return not self.issues


@dataclass
class SemanticFrame:
    """Parsed language turn used internally by the Language Cortex."""

    raw_text: str
    normalized_text: str
    intent: str
    entities: list[Entity] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    emotional_cue: str | None = None
    confidence: float = 0.5
    intent_prediction: IntentPrediction | None = None
    references: list[str] = field(default_factory=list)
    resolved_references: list[ReferenceResolution] = field(default_factory=list)
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_structured_input(self) -> StructuredInput:
        return StructuredInput(
            raw_text=self.raw_text,
            intent=self.intent,
            entities=list(self.entities),
            facts=list(self.facts),
            questions=list(self.questions),
            emotional_cue=self.emotional_cue,
            confidence=self.confidence,
            timestamp=self.timestamp,
        )


@dataclass
class DialogueTurn:
    user_text: str
    frame: SemanticFrame
    response: str = ""
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)


@dataclass
class ConversationState:
    session_id: str = "default"
    turns: list[DialogueTurn] = field(default_factory=list)
    active_topic: str | None = None
    last_intent: str | None = None
    slots: dict[str, Any] = field(default_factory=dict)

    def add_turn(self, turn: DialogueTurn) -> None:
        self.turns.append(turn)
        self.last_intent = turn.frame.intent
        topic = turn.frame.metadata.get("topic")
        if topic:
            self.active_topic = str(topic)
        for entity in turn.frame.entities:
            self.slots[entity.label.lower()] = entity.text

    def recent_context(self, limit: int = 4) -> list[DialogueTurn]:
        return self.turns[-limit:]
