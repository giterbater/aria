from __future__ import annotations

import asyncio

from aria_core.interfaces import StructuredInput
from language_cortex import (
    ConsistencyChecker,
    LanguageCortex,
    LanguageMemory,
    ResponsePlanner,
    SemanticGraph,
    SemanticParser,
)
from language_cortex.models.mock import MockModel


def run(coro):
    return asyncio.run(coro)


class TestSemanticParser:
    def test_intent_and_entity_extraction(self):
        frame = SemanticParser().parse("Open Calculator tomorrow")

        assert frame.intent == "open_application"
        assert any(e.label == "APP" and e.text.lower() == "calculator" for e in frame.entities)
        assert any(e.label == "TIME" and e.text.lower() == "tomorrow" for e in frame.entities)
        assert frame.confidence >= 0.8

    def test_question_and_emotion(self):
        parser = SemanticParser()

        question = parser.parse("What is ARIA?")
        emotion = parser.parse("I am feeling frustrated")

        assert question.intent == "question"
        assert question.questions == ["What is ARIA"]
        assert emotion.emotional_cue == "frustrated"
        assert any(e.label == "EMOTION" for e in emotion.entities)

    def test_remember_extracts_fact(self):
        frame = SemanticParser().parse("Remember that my project is ARIA")

        assert frame.intent == "remember"
        assert frame.facts == ["my project is ARIA"]

    def test_intent_prediction_includes_alternatives(self):
        frame = SemanticParser().parse("Can you search and summarize ARIA?")

        assert frame.intent_prediction is not None
        assert frame.intent_prediction.intent in {"question", "search"}
        assert frame.intent_prediction.alternative_intents

    def test_extracts_graph_facts(self):
        frame = SemanticParser().parse("I like Boxing")

        assert ("User", "likes", "Boxing") in frame.metadata["graph_facts"]


class TestSemanticGraph:
    def test_add_query_neighbors_and_search(self):
        graph = SemanticGraph()
        graph.add_fact("ARIA", "contains", "ReasoningEngine", confidence=0.9, source="test")
        graph.add_fact("ReasoningEngine", "uses", "Memory", confidence=0.8, source="test")

        assert graph.query(subject="ARIA")[0].object == "ReasoningEngine"
        assert any(fact.object == "Memory" for fact in graph.neighbors("ReasoningEngine"))
        assert graph.related_entities("ARIA")[0].label == "ReasoningEngine"
        assert graph.search("Memory")

    def test_remove_fact_and_persistence(self, tmp_path):
        path = tmp_path / "graph.json"
        graph = SemanticGraph(path)
        graph.add_fact("User", "likes", "Boxing", source="chat")

        loaded = SemanticGraph(path)
        assert loaded.query(subject="User", relation="likes")[0].object == "Boxing"
        assert loaded.remove_fact("User", "likes", "Boxing") is True
        assert loaded.query(subject="User") == []


class TestLanguageMemory:
    def test_fact_search(self):
        memory = LanguageMemory()
        memory.remember_fact("ARIA uses a language cortex")

        assert memory.search("language cortex") == ["ARIA uses a language cortex"]

    def test_long_conversation_summary_and_preferences(self):
        cortex = LanguageCortex(MockModel(), memory=LanguageMemory(summary_threshold=4))

        run(cortex.converse("I like boxing"))
        run(cortex.converse("Remember that ARIA is modular"))
        run(cortex.converse("What is ARIA?"))
        run(cortex.converse("Build a language layer"))

        assert cortex.memory.preferences()["likes"] == "boxing"
        assert cortex.memory.summaries()
        assert cortex.memory.conversational_goals()


class TestLanguageCortex:
    def test_interpret_returns_structured_input(self):
        cortex = LanguageCortex(MockModel())

        structured = run(cortex.interpret("How does memory work?"))

        assert isinstance(structured, StructuredInput)
        assert structured.intent == "question"
        assert structured.questions == ["How does memory work"]

    def test_converse_updates_state_and_memory(self):
        cortex = LanguageCortex(MockModel())

        first = run(cortex.converse("Remember that ARIA likes concise answers"))
        second = run(cortex.converse("What about that?"))

        assert first.frame.intent == "remember"
        assert cortex.memory.facts() == ["ARIA likes concise answers"]
        assert second.frame.metadata["resolved_reference"]
        assert cortex.state.last_intent == "question"
        assert second.response.startswith("Echo:")

    def test_converse_adds_graph_facts(self):
        cortex = LanguageCortex(MockModel())

        run(cortex.converse("User likes Boxing"))

        facts = cortex.semantic_graph.query(subject="User", relation="likes")
        assert facts and facts[0].object == "Boxing"

    def test_context_resolution_uses_recent_topic(self):
        cortex = LanguageCortex(MockModel())
        run(cortex.converse("Open calculator"))

        frame = cortex.parse("Can you close that?")
        context = cortex.resolve_context(frame)

        assert context["resolved_reference"]

    def test_previous_task_reference_resolution(self):
        cortex = LanguageCortex(MockModel())
        run(cortex.converse("Build a semantic graph"))

        frame = cortex.parse("Continue the previous task")
        context = cortex.resolve_context(frame)

        assert context["resolved_reference"] == "Build a semantic graph"

    def test_low_confidence_reference_requests_clarification(self):
        cortex = LanguageCortex(MockModel())

        turn = run(cortex.converse("Make it faster"))

        assert "referring" in turn.response.lower()
        assert cortex.clarification_rate() > 0

    def test_response_planning(self):
        cortex = LanguageCortex(MockModel())
        frame = cortex.parse("What about that?")
        context = cortex.resolve_context(frame)

        plan = cortex.plan_response(frame, context)

        assert plan.purpose == "answer_question"
        assert "resolved reference" in plan.missing_information
        assert plan.follow_up_questions

    def test_consistency_checker_detects_missing_reference(self):
        cortex = LanguageCortex(MockModel())
        frame = cortex.parse("Fix it")
        context = cortex.resolve_context(frame)
        plan = cortex.plan_response(frame, context)

        report = cortex.check_consistency("I will fix it.", frame, context, plan)

        assert not report.passed
        assert report.unresolved_pronouns

    def test_metrics_are_exposed(self):
        cortex = LanguageCortex(MockModel())
        run(cortex.converse("Open calculator"))
        run(cortex.converse("Close that"))

        assert cortex.intent_accuracy() >= 0
        assert cortex.entity_accuracy() >= 0
        assert cortex.reference_resolution_rate() > 0
        assert cortex.average_response_length() > 0
        assert cortex.conversation_depth() == 2
        assert cortex.context_resolution_rate() > 0

    def test_diagnostics_snapshot(self):
        cortex = LanguageCortex(MockModel())
        run(cortex.converse("Open calculator"))
        run(cortex.converse("Make it faster"))

        diagnostics = cortex.diagnostics()
        data = diagnostics.to_dict()

        assert diagnostics.conversation_depth == 2
        assert data["clarification_rate"] > 0
        assert data["intent_distribution"]
        assert "average_intent_confidence" in data


class TestProviderCompatibility:
    def test_existing_chat_api_still_uses_model_directly(self):
        cortex = LanguageCortex(MockModel())

        response = run(cortex.chat("hello"))

        assert response == "Echo: hello"
