"""
Tests for the SQLiteMemorySystem writeback of Outcome values.

Covers every Outcome enum value, importance clamping at the [0, 1]
boundaries, and the no-op behaviour for unknown episode IDs.
"""

import unittest

from aria_core.interfaces import ARIDecision, StructuredInput
from aria_core.memory.models import EpisodicItem, Outcome
from aria_core.memory.sqlite_memory_system import SQLiteMemorySystem


def _make_episode(importance: float = 0.5) -> EpisodicItem:
    si = StructuredInput(raw_text="hello", intent="statement")
    return EpisodicItem(
        structured_input=si,
        decision=ARIDecision(action_type="inform"),
        outcome=None,
        importance=importance,
    )


class TestOutcomeWriteback(unittest.TestCase):
    def setUp(self):
        self.mem = SQLiteMemorySystem()

    def tearDown(self):
        self.mem.close()

    def test_success_raises_importance_by_0_1(self):
        ep = _make_episode(importance=0.5)
        self.mem.store_episodic(ep)
        self.mem.record_outcome(ep.id, Outcome.SUCCESS)
        loaded = self.mem.get_episodic(limit=10)[0]
        self.assertAlmostEqual(loaded.importance, 0.6, places=5)
        self.assertEqual(loaded.outcome, "success")

    def test_partial_keeps_importance(self):
        ep = _make_episode(importance=0.5)
        self.mem.store_episodic(ep)
        self.mem.record_outcome(ep.id, Outcome.PARTIAL)
        loaded = self.mem.get_episodic(limit=10)[0]
        self.assertAlmostEqual(loaded.importance, 0.5, places=5)
        self.assertEqual(loaded.outcome, "partial")

    def test_failed_drops_importance_by_0_05(self):
        ep = _make_episode(importance=0.5)
        self.mem.store_episodic(ep)
        self.mem.record_outcome(ep.id, Outcome.FAILED)
        loaded = self.mem.get_episodic(limit=10)[0]
        self.assertAlmostEqual(loaded.importance, 0.45, places=5)
        self.assertEqual(loaded.outcome, "failed")

    def test_corrected_raises_importance_by_0_05(self):
        ep = _make_episode(importance=0.5)
        self.mem.store_episodic(ep)
        self.mem.record_outcome(ep.id, Outcome.CORRECTED)
        loaded = self.mem.get_episodic(limit=10)[0]
        self.assertAlmostEqual(loaded.importance, 0.55, places=5)
        self.assertEqual(loaded.outcome, "corrected")

    def test_ignored_drops_importance_by_0_05(self):
        ep = _make_episode(importance=0.5)
        self.mem.store_episodic(ep)
        self.mem.record_outcome(ep.id, Outcome.IGNORED)
        loaded = self.mem.get_episodic(limit=10)[0]
        self.assertAlmostEqual(loaded.importance, 0.45, places=5)
        self.assertEqual(loaded.outcome, "ignored")

    def test_success_clamps_at_1_0(self):
        ep = _make_episode(importance=0.97)
        self.mem.store_episodic(ep)
        self.mem.record_outcome(ep.id, Outcome.SUCCESS)
        loaded = self.mem.get_episodic(limit=10)[0]
        self.assertAlmostEqual(loaded.importance, 1.0, places=5)

    def test_failed_clamps_at_0_0(self):
        ep = _make_episode(importance=0.01)
        self.mem.store_episodic(ep)
        self.mem.record_outcome(ep.id, Outcome.FAILED)
        loaded = self.mem.get_episodic(limit=10)[0]
        self.assertAlmostEqual(loaded.importance, 0.0, places=5)

    def test_record_outcome_unknown_id_is_noop(self):
        # Must not raise; must not create a phantom row.
        self.mem.record_outcome("does-not-exist", Outcome.SUCCESS)
        self.assertEqual(self.mem.size()["episodic"], 0)

    def test_record_outcome_ignores_non_episodic_items(self):
        from aria_core.memory.models import SemanticItem
        sm = SemanticItem(fact="x", importance=0.5)
        self.mem.store_semantic(sm)
        # Calling record_outcome on a non-episodic id must be a no-op;
        # the importance should not change.
        original_imp = sm.importance
        self.mem.record_outcome(sm.id, Outcome.SUCCESS)
        loaded = self.mem.get_semantic()[0]
        self.assertAlmostEqual(loaded.importance, original_imp, places=5)
        # The fact must remain untouched (still a plain string).
        self.assertEqual(loaded.fact, "x")

    def test_record_outcome_with_notes_overwrites(self):
        ep = _make_episode(importance=0.5)
        ep_orig = self.mem.store_episodic(ep)
        self.mem.record_outcome(ep.id, Outcome.SUCCESS, notes="user said thanks")
        loaded = self.mem.get_episodic(limit=10)[0]
        self.assertEqual(loaded.outcome, "success")
        self.assertEqual(loaded.notes, "user said thanks")


if __name__ == "__main__":
    unittest.main()