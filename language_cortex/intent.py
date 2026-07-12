from __future__ import annotations

import re

from .schemas import IntentPrediction


class IntentDetector:
    """Deterministic intent detector for common ARIA language acts."""

    _QUESTION_RE = re.compile(r"\b(what|who|where|when|why|how|can|could|would|should|is|are|do|does)\b", re.I)
    _OPEN_RE = re.compile(r"\b(open|launch|start|run)\b", re.I)
    _CREATE_RE = re.compile(r"\b(create|write|make|draft|generate|build)\b", re.I)
    _SEARCH_RE = re.compile(r"\b(search|find|look up|lookup|research)\b", re.I)
    _REMEMBER_RE = re.compile(r"\b(remember|note that|keep in mind)\b", re.I)
    _SUMMARIZE_RE = re.compile(r"\b(summarize|recap|tl;dr)\b", re.I)
    _CLARIFY_RE = re.compile(r"\b(what do you mean|clarify|explain that|which one)\b", re.I)

    def predict(self, text: str) -> IntentPrediction:
        stripped = text.strip()
        if not stripped:
            return IntentPrediction("empty", 1.0)

        scores = {
            "remember": 0.9 if self._REMEMBER_RE.search(stripped) else 0.0,
            "open_application": 0.9 if self._OPEN_RE.search(stripped) else 0.0,
            "search": 0.85 if self._SEARCH_RE.search(stripped) else 0.0,
            "create": 0.82 if self._CREATE_RE.search(stripped) else 0.0,
            "summarize": 0.82 if self._SUMMARIZE_RE.search(stripped) else 0.0,
            "clarify": 0.8 if self._CLARIFY_RE.search(stripped) else 0.0,
            "question": 0.85 if stripped.endswith("?") or self._QUESTION_RE.match(stripped) else 0.0,
            "statement": 0.62,
        }
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        intent, confidence = ranked[0]
        alternatives = [(name, score) for name, score in ranked[1:4] if score > 0.0]
        ambiguities = []
        if alternatives and confidence - alternatives[0][1] < 0.12:
            ambiguities.append(f"Could be {intent} or {alternatives[0][0]}")
        if any(word in stripped.lower().split() for word in ("it", "that", "this")) and intent in {"statement", "create", "open_application"}:
            ambiguities.append("Contains a reference that needs context")

        return IntentPrediction(
            intent=intent,
            confidence=confidence,
            alternative_intents=alternatives,
            ambiguities=ambiguities,
            requires_clarification=confidence < 0.68 or bool(ambiguities and confidence < 0.85),
        )

    def detect(self, text: str) -> tuple[str, float]:
        prediction = self.predict(text)
        return prediction.intent, prediction.confidence
