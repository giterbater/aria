from __future__ import annotations

import re

from .entities import EntityExtractor
from .intent import IntentDetector
from .schemas import SemanticFrame


class SemanticParser:
    """Parse raw user text into a semantic frame."""

    _REFERENCE_RE = re.compile(r"\b(it|that|this|they|them|there|he|she|previous task|last task|previous|continue)\b", re.I)
    _RELATION_FACTS = [
        re.compile(r"\b(?:i|user)\s+(like|likes|love|loves|prefer|prefers)\s+(.+)", re.I),
        re.compile(r"\b(?:i am|i'm|user is)\s+(building|making|creating|working on)\s+(.+)", re.I),
        re.compile(r"\b([A-Z][A-Za-z0-9_ -]+)\s+(contains|uses|includes|has)\s+([A-Z][A-Za-z0-9_ -]+)\b"),
    ]

    def __init__(
        self,
        intent_detector: IntentDetector | None = None,
        entity_extractor: EntityExtractor | None = None,
    ) -> None:
        self._intent = intent_detector or IntentDetector()
        self._entities = entity_extractor or EntityExtractor()

    def parse(self, raw_text: str) -> SemanticFrame:
        normalized = self._normalize(raw_text)
        prediction = self._intent.predict(normalized)
        intent, confidence = prediction.intent, prediction.confidence
        entities = self._entities.extract(raw_text)
        questions = [raw_text.strip().rstrip("?")] if intent == "question" or raw_text.strip().endswith("?") else []
        facts = self._extract_facts(raw_text, intent)
        emotional_cue = next((e.text for e in entities if e.label == "EMOTION"), None)
        references = [m.group(1).lower() for m in self._REFERENCE_RE.finditer(raw_text)]
        graph_facts = self._extract_graph_facts(raw_text)

        return SemanticFrame(
            raw_text=raw_text,
            normalized_text=normalized,
            intent=intent,
            entities=entities,
            facts=facts,
            questions=questions,
            emotional_cue=emotional_cue,
            confidence=confidence,
            intent_prediction=prediction,
            references=references,
            metadata={"topic": self._topic(normalized, entities), "graph_facts": graph_facts},
        )

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.strip().split()).lower()

    @staticmethod
    def _extract_facts(text: str, intent: str) -> list[str]:
        stripped = text.strip()
        if not stripped or intent in {"question", "empty"}:
            return []
        if intent == "remember":
            lowered = stripped.lower()
            for prefix in ("remember that", "remember", "note that", "keep in mind"):
                if lowered.startswith(prefix):
                    return [stripped[len(prefix):].strip(" :")]
        return [stripped] if intent == "statement" else []

    @classmethod
    def _extract_graph_facts(cls, text: str) -> list[tuple[str, str, str]]:
        facts: list[tuple[str, str, str]] = []
        for pattern in cls._RELATION_FACTS:
            match = pattern.search(text)
            if not match:
                continue
            if len(match.groups()) == 2:
                relation, obj = match.groups()
                facts.append(("User", cls._normalize_relation(relation), obj.strip(" .")))
            else:
                subject, relation, obj = match.groups()
                facts.append((subject.strip(" ."), cls._normalize_relation(relation), obj.strip(" .")))
        return facts

    @staticmethod
    def _normalize_relation(relation: str) -> str:
        relation = relation.lower().strip()
        return {
            "like": "likes",
            "love": "likes",
            "loves": "likes",
            "prefer": "prefers",
            "building": "building",
            "making": "building",
            "creating": "building",
            "working on": "building",
        }.get(relation, relation)

    @staticmethod
    def _topic(normalized: str, entities) -> str | None:
        for entity in entities:
            if entity.label in {"APP", "PERSON", "PATH"}:
                return entity.text
        stop = {
            "what", "about", "that", "this", "there", "they", "them", "with",
            "when", "where", "which", "continue", "previous", "make", "faster",
        }
        tokens = [t for t in re.findall(r"[a-z0-9_]+", normalized) if len(t) > 3 and t not in stop]
        return " ".join(tokens[:4]) if tokens else None
