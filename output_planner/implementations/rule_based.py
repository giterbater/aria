from ..interfaces import OutputPlannerProtocol
from aria_core.interfaces import ARIDecision

class RuleBasedOutputPlanner:
    """Simple heuristic planner: maps decision fields to communication plan."""
    # Mapping from action_type to default tone/priority
    DEFAULTS = {
        "warn": {"urgency": "high", "tone": "calm", "priority": "high"},
        "inform": {"urgency": "normal", "tone": "neutral", "priority": "normal"},
        "query": {"urgency": "normal", "tone": "friendly", "priority": "normal"},
        "execute": {"urgency": "low", "tone": "neutral", "priority": "low"},
    }

    async def plan(self, decision: ARIDecision) -> dict:
        base = self.DEFAULTS.get(decision.action_type, {"urgency": "normal", "tone": "neutral", "priority": "normal"})
        # Override with any explicit fields the core may have set
        urgency = decision.urgency or base["urgency"]
        tone = decision.tone or base["tone"]
        priority = decision.priority or base["priority"]

        # Build a prompt for the Language Cortex
        prompt_parts = []
        if decision.action_type == "inform":
            prompt_parts.append(f"Please inform the user: {decision.payload.get('message', '')}")
        elif decision.action_type == "warn":
            prompt_parts.append(f"Give a calm but urgent warning: {decision.payload.get('message', '')}")
        elif decision.action_type == "query":
            prompt_parts.append(f"Answer the user's question: {decision.payload.get('question', '')}")
        elif decision.action_type == "execute":
            prompt_parts.append(f"Confirm that you have executed: {decision.payload.get('action', '')}")
        else:
            prompt_parts.append(str(decision.payload))

        prompt = " ".join(filter(None, prompt_parts)).strip()
        if not prompt:
            prompt = "Please respond appropriately."

        # Length hint – short vs long
        length_hint = "short" if len(prompt) < 120 else "medium"
        # Temperature/token hints based on tone
        temperature = {"friendly": 0.8, "formal": 0.5, "empathetic": 0.7, "calm": 0.6, "neutral": 0.7}.get(tone, 0.7)
        max_tokens = 60 if length_hint == "short" else 120

        return {
            "prompt": prompt,
            "speak": decision.speak,
            "priority": priority,
            "urgency": urgency,
            "tone": tone,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }