from __future__ import annotations

from .schemas import ResponsePlan, SemanticFrame


class ResponsePlanner:
    """Create a structured response plan before language generation."""

    def plan(self, frame: SemanticFrame, context: dict) -> ResponsePlan:
        tone = "empathetic" if frame.emotional_cue else "neutral"
        purpose = self._purpose(frame)
        required = ["user request", "current intent"]
        missing: list[str] = []
        followups: list[str] = []

        if frame.references and not context.get("resolved_reference"):
            missing.append("resolved reference")
            followups.append("What are you referring to?")

        prediction = frame.intent_prediction
        if prediction and prediction.requires_clarification:
            missing.append("clarified user intent")
            if not followups:
                followups.append("Could you clarify what you want me to do?")

        if frame.intent == "question" and not (context.get("relevant_facts") or context.get("related_entities")):
            required.append("answer grounded in available context")

        structure = ["acknowledge"]
        if missing:
            structure.append("ask clarification")
        else:
            structure.append("answer")
        if frame.intent in {"create", "search", "summarize", "open_application"}:
            structure.append("confirm next step")

        return ResponsePlan(
            purpose=purpose,
            tone=tone,
            required_information=required,
            missing_information=missing,
            citations_needed=self._needs_citations(frame),
            response_structure=structure,
            follow_up_questions=followups,
        )

    @staticmethod
    def _purpose(frame: SemanticFrame) -> str:
        return {
            "question": "answer_question",
            "remember": "confirm_memory",
            "open_application": "confirm_requested_action",
            "create": "clarify_or_confirm_creation",
            "search": "clarify_or_answer_search",
            "summarize": "summarize_context",
            "clarify": "clarify_previous_context",
            "empty": "request_rephrase",
        }.get(frame.intent, "respond")

    @staticmethod
    def _needs_citations(frame: SemanticFrame) -> bool:
        text = frame.normalized_text
        return frame.intent in {"search", "question"} and any(
            word in text for word in ("source", "cite", "latest", "today", "evidence")
        )
