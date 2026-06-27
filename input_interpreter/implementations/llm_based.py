from ..interfaces import InputInterpreterProtocol
from aria_core.interfaces import StructuredInput, Entity
from language_cortex.manager import LanguageCortex   # reuse the Language Cortex

class LLMBasedInputInterpreter:
    def __init__(self, language_cortex: LanguageCortex):
        self.lm = language_cortex

    async def interpret(self, raw_text: str) -> StructuredInput:
        prompt = f"""
You are an input interpreter for ARIA. Extract the following fields from the user utterance and return a JSON object:
- intent (string)
- entities (list of objects with "text" and "label")
- facts (list of strings)
- questions (list of strings)
- emotional_cue (string or null)
- confidence (float between 0 and 1)

Utterance: \"\"\"{raw_text}\"\"\"

Return ONLY the JSON, no extra text.
"""
        json_str = await self.lm.chat(prompt, temperature=0.0)
        import json
        data = json.loads(json_str)

        entities = [Entity(**e) for e in data.get("entities", [])]
        return StructuredInput(
            raw_text=raw_text,
            intent=data.get("intent", "statement"),
            entities=entities,
            facts=data.get("facts", []),
            questions=data.get("questions", []),
            emotional_cue=data.get("emotional_cue"),
            confidence=float(data.get("confidence", 0.8)),
        )