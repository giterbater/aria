import unittest

from aria_core.interfaces import StructuredInput, ARIDecision, Entity
from aria_core.memory.models import (
    WorkingMemoryItem,
    EpisodicItem,
    SemanticItem,
)
from aria_core.memory.simple_memory_system import SimpleMemorySystem


class TestSemanticRetrieval(unittest.TestCase):
    def test_semantic_query_matches_raw_text_in_fact(self):
        mem = SimpleMemorySystem()
        si_fact = {"raw_text": "ARIA uses a modular architecture", "intent": "statement"}
        item = SemanticItem(fact=si_fact, importance=0.5)
        mem.store_semantic(item)

        results = mem.get_semantic(query="modular architecture")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].fact, si_fact)

    def test_semantic_query_matches_fact_list(self):
        mem = SimpleMemorySystem()
        facts = ["ARIA has memory", "ARIA has goals"]
        item = SemanticItem(fact=facts, importance=0.5)
        mem.store_semantic(item)

        results = mem.get_semantic(query="memory goals")
        self.assertEqual(len(results), 1)

    def test_semantic_query_no_match_returns_empty(self):
        mem = SimpleMemorySystem()
        item = SemanticItem(fact="some unrelated fact", importance=0.5)
        mem.store_semantic(item)

        results = mem.get_semantic(query="quantum physics")
        self.assertEqual(len(results), 0)


class TestRetrieveRelevant(unittest.TestCase):
    def test_retrieve_relevant_ranks_matching_raw_text_above_unrelated(self):
        mem = SimpleMemorySystem()
        matching_si = StructuredInput(
            raw_text="open the calculator app",
            intent="open_application",
            facts=["calculator is useful"],
        )
        unrelated_si = StructuredInput(
            raw_text="what time is it",
            intent="question",
        )
        wm_match = WorkingMemoryItem(structured_input=matching_si, importance=0.5)
        wm_unrelated = WorkingMemoryItem(structured_input=unrelated_si, importance=0.5)
        mem.store_working(wm_match)
        mem.store_working(wm_unrelated)

        results = mem.retrieve_relevant("calculator")
        self.assertTrue(len(results) >= 2)
        self.assertEqual(results[0][0].id, wm_match.id)
        self.assertGreater(results[0][1], results[1][1])

    def test_retrieve_relevant_ranks_episodic_matching_above_unrelated(self):
        mem = SimpleMemorySystem()
        matching_si = StructuredInput(
            raw_text="play some jazz music",
            intent="play_music",
        )
        unrelated_si = StructuredInput(
            raw_text="search the web",
            intent="question",
        )
        em_match = EpisodicItem(structured_input=matching_si, importance=0.5)
        em_unrelated = EpisodicItem(structured_input=unrelated_si, importance=0.5)
        mem.store_episodic(em_match)
        mem.store_episodic(em_unrelated)

        results = mem.retrieve_relevant("jazz music")
        self.assertTrue(len(results) >= 2)
        self.assertEqual(results[0][0].id, em_match.id)
        self.assertGreater(results[0][1], results[1][1])


class TestUpdateImportancePreservesType(unittest.TestCase):
    def _make_system(self):
        return SimpleMemorySystem()

    def test_working_memory_item_preserves_type(self):
        mem = self._make_system()
        ctx = {"key": "value"}
        si = StructuredInput(raw_text="hello world", intent="statement")
        wm = WorkingMemoryItem(structured_input=si, context=ctx, importance=0.5)
        mem.store_working(wm)

        mem.update_importance(wm.id, 0.3)
        results = mem.get_working(limit=1)
        updated = results[0]

        self.assertIsInstance(updated, WorkingMemoryItem)
        self.assertAlmostEqual(updated.importance, 0.8, places=5)
        self.assertEqual(updated.id, wm.id)
        self.assertEqual(updated.structured_input, si)
        self.assertEqual(updated.context, ctx)

    def test_episodic_item_preserves_type(self):
        mem = self._make_system()
        si = StructuredInput(raw_text="test input", intent="statement")
        decision = ARIDecision(action_type="inform", payload={"msg": "hi"})
        em = EpisodicItem(
            structured_input=si,
            decision=decision,
            outcome="success",
            notes="user was happy",
            importance=0.4,
        )
        mem.store_episodic(em)

        mem.update_importance(em.id, 0.2)
        # retrieve from episodic store directly
        updated_list = mem.get_episodic(limit=1)
        updated = updated_list[0]

        self.assertIsInstance(updated, EpisodicItem)
        self.assertAlmostEqual(updated.importance, 0.6, places=5)
        self.assertEqual(updated.id, em.id)
        self.assertEqual(updated.structured_input, si)
        self.assertEqual(updated.decision, decision)
        self.assertEqual(updated.outcome, "success")
        self.assertEqual(updated.notes, "user was happy")

    def test_semantic_item_preserves_type(self):
        mem = self._make_system()
        si_fact = {"raw_text": "fact about ARIA", "intent": "statement"}
        sm = SemanticItem(
            fact=si_fact,
            source_episodic_ids=["ep-1", "ep-2"],
            confidence=0.9,
            importance=0.3,
        )
        mem.store_semantic(sm)

        mem.update_importance(sm.id, 0.4)
        # retrieve by searching for it
        updated_list = mem.get_semantic(query="fact about ARIA")
        self.assertEqual(len(updated_list), 1)
        updated = updated_list[0]

        self.assertIsInstance(updated, SemanticItem)
        self.assertAlmostEqual(updated.importance, 0.7, places=5)
        self.assertEqual(updated.id, sm.id)
        self.assertEqual(updated.fact, si_fact)
        self.assertEqual(updated.source_episodic_ids, ["ep-1", "ep-2"])
        self.assertAlmostEqual(updated.confidence, 0.9, places=5)

    def test_importance_is_clamped_to_valid_range(self):
        mem = self._make_system()
        wm = WorkingMemoryItem(importance=0.9)
        mem.store_working(wm)

        mem.update_importance(wm.id, 5.0)
        updated = mem.get_working(limit=1)[0]
        self.assertAlmostEqual(updated.importance, 1.0, places=5)

        mem.update_importance(wm.id, -10.0)
        updated2 = mem.get_working(limit=1)[0]
        self.assertAlmostEqual(updated2.importance, 0.0, places=5)


class TestExtractTextHelper(unittest.TestCase):
    def test_extract_from_structured_input(self):
        from aria_core.memory.simple_memory_system import _extract_text

        si = StructuredInput(
            raw_text="open calculator",
            intent="open_application",
            entities=[Entity(text="calculator", label="APP")],
            facts=["calculator is useful"],
            emotional_cue="excited",
        )
        text = _extract_text(si)
        self.assertIn("open calculator", text)
        self.assertIn("open_application", text)
        self.assertIn("calculator", text)
        self.assertIn("useful", text)
        self.assertIn("excited", text)

    def test_extract_from_dict(self):
        from aria_core.memory.simple_memory_system import _extract_text

        d = {"raw_text": "hello", "intent": "greeting", "emotional_cue": "happy"}
        text = _extract_text(d)
        self.assertIn("hello", text)
        self.assertIn("greeting", text)
        self.assertIn("happy", text)

    def test_extract_from_decision(self):
        from aria_core.memory.simple_memory_system import _extract_text

        dec = ARIDecision(action_type="execute", payload={"action": "launch_calc"})
        text = _extract_text(dec)
        self.assertIn("execute", text)
        self.assertIn("launch_calc", text)

    def test_extract_from_nested_list(self):
        from aria_core.memory.simple_memory_system import _extract_text

        nested = ["first fact", {"raw_text": "nested text"}, None]
        text = _extract_text(nested)
        self.assertIn("first fact", text)
        self.assertIn("nested text", text)

    def test_extract_none(self):
        from aria_core.memory.simple_memory_system import _extract_text

        self.assertEqual(_extract_text(None), "")

    def test_extract_plain_string(self):
        from aria_core.memory.simple_memory_system import _extract_text

        self.assertEqual(_extract_text("hello world"), "hello world")


if __name__ == "__main__":
    unittest.main()
