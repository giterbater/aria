from ..interfaces import OutputPlannerProtocol
from aria_core.interfaces import ARIDecision
from language_cortex.manager import LanguageCortex

class LLMBasedOutputPlanner:
    """
    Uses the Language Cortex to decide how to communicate a decision.
    Returns a dict with prompt, speak, etc.
    """
    def __init__(self, language_cortex: LanguageCortex):
        self.lm = language_cortex

    async def plan(self, decision: ARIDecision) -> dict:
        # Ask the language model to produce a plan in JSON format
        prompt = f"""
You are ARIA's Output Planner. Given the following decision, produce a JSON plan for how to communicate it.
Decision: {decision}

Return a JSON object with keys:
- prompt: string (what to send to the Language Cortex to generate the cortex to speak)
- speak: boolean (whether to actually speak the result)
- priority: "low"|"normal"|"high"
- urgency: "low"|"normal"|"high"
- tone: "neutral"|"friendly"|"formal"|"empathetic"|"calm"
- max_tokens: integer (suggested limit for language generation)
- temperature: float (0.0-1.0)

Only output valid JSON.
"""
        import json
        json_str = await self.lm.chat(prompt, temperature=0.0)
        plan = json.loads(json_str)
        # Ensure required keys exist
        plan.setdefault("prompt", str(decision.payload))
        plan.setdefault("speak", decision.speak)
        return plan