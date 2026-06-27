import re
from typing import List
from ..interfaces import InputInterpreterProtocol
from aria_core.interfaces import StructuredInput, Entity

class RuleBasedInputInterpreter:
    """Very simple intent/entity extraction using regexes."""
    INTENT_PATTERNS = {
        r"\b(open|launch|start)\s+(.+)": ("open_application", lambda m: [Entity(m.group(2).strip(), "APP")]),
        r"\b(what|who|where|when|why|how)\b": ("question", lambda m: []),
        r"\b(i feel|i am feeling)\s+(.+)": ("statement", lambda m: [Entity(m.group(2).strip(), "EMOTION")]),
    }

    async def interpret(self, raw_text: str) -> StructuredInput:
        text = raw_text.strip().lower()
        intent = "statement"
        entities: List[Entity] = []
        facts = []
        questions = []
        emotional_cue = None
        confidence = 0.5

        for pattern, (intent_name, ent_fn) in self.INTENT_PATTERNS.items():
            m = re.search(pattern, text)
            if m:
                intent = intent_name
                entities.extend(ent_fn(m))
                confidence = 0.9
                break

        # Very naive question detection
        if text.endswith("?") or intent == "question":
            questions.append(text.rstrip("?"))
            confidence = max(confidence, 0.8)

        # Emotional cue detection (very simple)
        emo_match = re.search(r"\b(i feel|i am feeling)\s+(.+)", text)
        if emo_match:
            emotional_cue = emo_match.group(2).strip()
            confidence = max(confidence, 0.85)

        return StructuredInput(
            raw_text=raw_text,
            intent=intent,
            entities=entities,
            facts=facts,
            questions=questions,
            emotional_cue=emotional_cue,
            confidence=confidence,
        )