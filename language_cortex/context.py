from __future__ import annotations

from .memory import LanguageMemory
from .schemas import ConversationState, ReferenceResolution, SemanticFrame
from .semantic_graph import SemanticGraph


class ContextResolver:
    """Resolve lightweight discourse context for the current turn."""

    def __init__(self, memory: LanguageMemory, graph: SemanticGraph | None = None) -> None:
        self._memory = memory
        self._graph = graph or SemanticGraph()

    def resolve(self, frame: SemanticFrame, state: ConversationState) -> dict:
        topic = frame.metadata.get("topic") or state.active_topic or self._memory.latest_topic()
        relevant_facts = self._memory.search(frame.normalized_text, limit=5)
        resolutions = self._resolve_references(frame, state, topic)

        if resolutions:
            frame.resolved_references = resolutions
            best = max(resolutions, key=lambda item: item.confidence)
            if best.resolved_text:
                frame.metadata["resolved_reference"] = best.resolved_text

        return {
            "topic": topic,
            "resolved_reference": frame.metadata.get("resolved_reference"),
            "reference_resolutions": resolutions,
            "relevant_facts": relevant_facts,
            "related_entities": [n.label for n in self._graph.related_entities(str(topic), limit=5)] if topic else [],
            "recent_turns": [
                {"user": turn.user_text, "response": turn.response}
                for turn in state.recent_context()
            ],
            "slots": dict(state.slots),
            "active_subjects": self._memory.active_subjects(),
            "recent_topics": self._memory.recent_topics(),
            "preferences": self._memory.preferences(),
            "unresolved_questions": self._memory.unresolved_questions(),
            "conversational_goals": self._memory.conversational_goals(),
        }

    def _resolve_references(
        self,
        frame: SemanticFrame,
        state: ConversationState,
        topic: str | None,
    ) -> list[ReferenceResolution]:
        resolutions: list[ReferenceResolution] = []
        for reference in frame.references:
            resolved = None
            source = "unresolved"
            confidence = 0.0

            if reference in {"previous task", "last task", "previous", "continue"}:
                goals = self._memory.conversational_goals(limit=1)
                if goals:
                    resolved, source, confidence = goals[-1], "conversation_goal", 0.9
            elif reference in {"it", "that", "this", "they", "them", "there"}:
                subjects = self._memory.active_subjects(limit=1)
                if subjects:
                    resolved, source, confidence = subjects[-1], "active_subject", 0.86
                elif topic:
                    resolved, source, confidence = topic, "topic", 0.8
            elif reference in {"he", "she", "him"}:
                person = state.slots.get("person")
                if person:
                    resolved, source, confidence = str(person), "slot", 0.84

            if not resolved and topic:
                related = self._graph.related_entities(topic, limit=1)
                if related:
                    resolved, source, confidence = related[0].label, "semantic_graph", 0.72

            resolutions.append(ReferenceResolution(reference, resolved, source, confidence))
        return resolutions
