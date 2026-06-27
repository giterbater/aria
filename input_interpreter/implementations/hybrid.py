from ..interfaces import InputInterpreterProtocol
from .rule_based import RuleBasedInputInterpreter
from .llm_based import LLMBasedInputInterpreter
from aria_core.interfaces import StructuredInput

class HybridInputInterpreter:
    """
    Tries rule‑based first; if confidence < threshold, delegates to LLM fallback.
    """
    def __init__(
        self,
        rule_based: RuleBasedInputInterpreter,
        llm_fallback: LLMBasedInputInterpreter,
        confidence_threshold: float = 0.85,
    ) -> None:
        self._rule = rule_based
        self._llm = llm_fallback
        self._threshold = confidence_threshold

    async def interpret(self, raw_text: str) -> StructuredInput:
        rule_result = await self._rule.interpret(raw_text)
        if rule_result.confidence >= self._threshold:
            return rule_result
        # fallback
        return await self._llm.interpret(raw_text)