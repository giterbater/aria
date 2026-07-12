from __future__ import annotations

from .consistency import ConsistencyChecker
from .interfaces import LanguageModel
from .response_planner import ResponsePlanner
from .schemas import ResponsePlan, SemanticFrame


class ResponseGenerator:
    """Generate user-facing responses from semantic and dialogue context."""

    def __init__(
        self,
        model: LanguageModel,
        *,
        planner: ResponsePlanner | None = None,
        checker: ConsistencyChecker | None = None,
    ) -> None:
        self._model = model
        self._planner = planner or ResponsePlanner()
        self._checker = checker or ConsistencyChecker()

    async def generate(
        self,
        frame: SemanticFrame,
        context: dict,
        *,
        max_tokens: int = 160,
        temperature: float = 0.7,
    ) -> str:
        plan = self.plan(frame, context)
        if plan.requires_clarification and plan.follow_up_questions:
            draft = plan.follow_up_questions[0]
        else:
            prompt = self.build_prompt(frame, context, plan)
            draft = await self._model.generate(prompt, max_tokens=max_tokens, temperature=temperature)
        report = self._checker.check(draft, frame, context, plan)
        return self._checker.improve(draft, report, plan)

    def plan(self, frame: SemanticFrame, context: dict) -> ResponsePlan:
        return self._planner.plan(frame, context)

    def build_prompt(self, frame: SemanticFrame, context: dict, plan: ResponsePlan | None = None) -> str:
        plan = plan or self.plan(frame, context)
        parts = [
            "You are ARIA's language cortex. Respond clearly and conversationally.",
            plan.to_prompt_section(),
            f"Intent: {frame.intent}",
            f"User: {frame.raw_text}",
        ]
        if frame.entities:
            parts.append("Entities: " + ", ".join(f"{e.label}={e.text}" for e in frame.entities))
        if frame.emotional_cue:
            parts.append(f"Emotional cue: {frame.emotional_cue}")
        if context.get("topic"):
            parts.append(f"Current topic: {context['topic']}")
        if context.get("resolved_reference"):
            parts.append(f"Resolved reference: {context['resolved_reference']}")
        if context.get("relevant_facts"):
            parts.append("Relevant memory: " + " | ".join(context["relevant_facts"]))
        if context.get("related_entities"):
            parts.append("Related entities: " + ", ".join(context["related_entities"]))
        parts.append("Reply:")
        return "\n".join(parts)

    def fallback(self, frame: SemanticFrame, context: dict) -> str:
        if frame.intent == "empty":
            return "I did not catch anything. Try saying that again."
        if frame.intent == "remember":
            return "Got it. I will remember that."
        if frame.intent == "open_application":
            app = next((e.text for e in frame.entities if e.label == "APP"), "that app")
            return f"I understand you want to open {app}."
        if frame.intent == "question":
            topic = context.get("topic") or "that"
            return f"You are asking about {topic}."
        if frame.emotional_cue:
            return f"I hear that you are feeling {frame.emotional_cue}."
        return "I understand."
