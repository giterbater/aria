from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .schemas import DialogueTurn, SemanticFrame


@dataclass(frozen=True)
class LanguageDiagnostics:
    intent_accuracy: float
    entity_accuracy: float
    reference_resolution_rate: float
    average_response_length: float
    conversation_depth: int
    clarification_rate: float
    context_resolution_rate: float
    unresolved_references: int
    low_confidence_intents: int
    average_intent_confidence: float
    intent_distribution: dict[str, int] = field(default_factory=dict)
    ambiguity_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_accuracy": self.intent_accuracy,
            "entity_accuracy": self.entity_accuracy,
            "reference_resolution_rate": self.reference_resolution_rate,
            "average_response_length": self.average_response_length,
            "conversation_depth": self.conversation_depth,
            "clarification_rate": self.clarification_rate,
            "context_resolution_rate": self.context_resolution_rate,
            "unresolved_references": self.unresolved_references,
            "low_confidence_intents": self.low_confidence_intents,
            "average_intent_confidence": self.average_intent_confidence,
            "intent_distribution": dict(self.intent_distribution),
            "ambiguity_count": self.ambiguity_count,
        }


@dataclass
class LanguageMetrics:
    intents_total: int = 0
    intents_correct: int = 0
    entities_total: int = 0
    entities_correct: int = 0
    references_total: int = 0
    references_resolved: int = 0
    responses_total: int = 0
    response_chars: int = 0
    turns_total: int = 0
    clarifications: int = 0
    context_attempts: int = 0
    context_resolved: int = 0
    unresolved_references: int = 0
    low_confidence_intents: int = 0
    intent_confidence_total: float = 0.0
    intent_distribution: dict[str, int] = field(default_factory=dict)
    ambiguity_count: int = 0

    def record_frame(self, frame: SemanticFrame) -> None:
        self.intents_total += 1
        self.intent_distribution[frame.intent] = self.intent_distribution.get(frame.intent, 0) + 1
        self.intent_confidence_total += frame.confidence
        if frame.confidence < 0.6:
            self.low_confidence_intents += 1
        if frame.intent_prediction:
            self.ambiguity_count += len(frame.intent_prediction.ambiguities)
        if frame.intent_prediction and not frame.intent_prediction.requires_clarification:
            self.intents_correct += 1
        self.entities_total += len(frame.entities)
        self.entities_correct += len([e for e in frame.entities if e.confidence >= 0.75])
        self.references_total += len(frame.references)
        self.references_resolved += len([r for r in frame.resolved_references if r.resolved_text])
        self.unresolved_references += len([r for r in frame.resolved_references if not r.resolved_text])
        if frame.references:
            self.context_attempts += 1
            if any(r.resolved_text for r in frame.resolved_references):
                self.context_resolved += 1
        if frame.intent_prediction and frame.intent_prediction.requires_clarification:
            self.clarifications += 1

    def record_turn(self, turn: DialogueTurn) -> None:
        self.turns_total += 1
        if turn.response:
            self.responses_total += 1
            self.response_chars += len(turn.response)

    def intent_accuracy(self) -> float:
        return self._ratio(self.intents_correct, self.intents_total)

    def entity_accuracy(self) -> float:
        return self._ratio(self.entities_correct, self.entities_total)

    def reference_resolution_rate(self) -> float:
        return self._ratio(self.references_resolved, self.references_total)

    def average_response_length(self) -> float:
        return self._ratio(self.response_chars, self.responses_total)

    def conversation_depth(self) -> int:
        return self.turns_total

    def clarification_rate(self) -> float:
        return self._ratio(self.clarifications, self.intents_total)

    def context_resolution_rate(self) -> float:
        return self._ratio(self.context_resolved, self.context_attempts)

    def average_intent_confidence(self) -> float:
        return self._ratio(self.intent_confidence_total, self.intents_total)

    def diagnostics(self) -> LanguageDiagnostics:
        return LanguageDiagnostics(
            intent_accuracy=self.intent_accuracy(),
            entity_accuracy=self.entity_accuracy(),
            reference_resolution_rate=self.reference_resolution_rate(),
            average_response_length=self.average_response_length(),
            conversation_depth=self.conversation_depth(),
            clarification_rate=self.clarification_rate(),
            context_resolution_rate=self.context_resolution_rate(),
            unresolved_references=self.unresolved_references,
            low_confidence_intents=self.low_confidence_intents,
            average_intent_confidence=self.average_intent_confidence(),
            intent_distribution=dict(self.intent_distribution),
            ambiguity_count=self.ambiguity_count,
        )

    def to_dict(self) -> dict[str, Any]:
        return self.diagnostics().to_dict()

    @staticmethod
    def _ratio(numerator: float, denominator: float) -> float:
        return numerator / denominator if denominator else 0.0
