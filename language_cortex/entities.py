from __future__ import annotations

import re

from aria_core.interfaces import Entity


class EntityExtractor:
    """Rule-based entity extraction with stable labels used by ARIA Core."""

    _APP_RE = re.compile(r"\b(?:open|launch|start|run)\s+([a-zA-Z0-9_. -]+)", re.I)
    _EMOTION_RE = re.compile(r"\b(?:i feel|i am feeling|i'm feeling|i am|i'm)\s+(sad|happy|angry|excited|frustrated|tired|worried|anxious|stuck)\b", re.I)
    _TIME_RE = re.compile(r"\b(today|tomorrow|tonight|yesterday|next week|in \d+ (?:minutes?|hours?|days?)|at \d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b", re.I)
    _PERSON_RE = re.compile(r"\b(?:with|for|to|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b")
    _PATH_RE = re.compile(r"(?P<path>(?:[A-Za-z]:\\|/)?[\w .-]+[/\\][\w .-]+)")
    _TRAILING_TIME_RE = re.compile(r"\s+\b(today|tomorrow|tonight|next week|in \d+ (?:minutes?|hours?|days?)|at \d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b.*$", re.I)

    def extract(self, text: str) -> list[Entity]:
        entities: list[Entity] = []
        app_match = self._APP_RE.search(text)
        if app_match:
            app = self._TRAILING_TIME_RE.sub("", app_match.group(1)).strip(" .")
            if app:
                entities.append(Entity(app, "APP", 0.88))
        self._append_match(entities, self._EMOTION_RE.search(text), "EMOTION")
        self._append_match(entities, self._TIME_RE.search(text), "TIME")
        self._append_match(entities, self._PERSON_RE.search(text), "PERSON")

        for match in self._PATH_RE.finditer(text):
            path = match.group("path").strip()
            if path:
                entities.append(Entity(path, "PATH", 0.86))

        return self._dedupe(entities)

    @staticmethod
    def _append_match(entities: list[Entity], match: re.Match | None, label: str) -> None:
        if match:
            entities.append(Entity(match.group(1).strip(" ."), label, 0.88))

    @staticmethod
    def _dedupe(entities: list[Entity]) -> list[Entity]:
        seen: set[tuple[str, str]] = set()
        out: list[Entity] = []
        for entity in entities:
            key = (entity.text.lower(), entity.label)
            if key not in seen:
                seen.add(key)
                out.append(entity)
        return out
