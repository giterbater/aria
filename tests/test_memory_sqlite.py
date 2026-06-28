"""
Tests for the SQLiteMemorySystem implementation of MemorySystemProtocol.

Exercises every protocol method against :memory: and a real on-disk
file, verifies subtype preservation across round-trip, and confirms
the system is a runtime_checkable Protocol.
"""

import os
import tempfile
import unittest

from aria_core.interfaces import ARIDecision, StructuredInput
from aria_core.memory.interfaces import MemorySystemProtocol
from aria_core.memory.models import (
    EpisodicItem,
    Outcome,
    SemanticItem,
    WorkingMemoryItem,
)
from aria_core.memory.sqlite_memory_system import SQLiteMemorySystem


def _temp_db() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    return path


class TestMemoryProtocolConformance(unittest.TestCase):
    """Verify SQLiteMemorySystem satisfies MemorySystemProtocol."""

    def test_isinstance_memory_system_protocol(self):
        mem = SQLiteMemorySystem()
        try:
            self.assertIsInstance(mem, MemorySystemProtocol)
        finally:
            mem.close()


class TestWorkingStore(unittest.TestCase):
    def setUp(self):
        self.mem = SQLiteMemorySystem()

    def tearDown(self):
        self.mem.close()

    def test_store_and_get_working_round_trip(self):
        si = StructuredInput(raw_text="hi", intent="statement")
        wm = WorkingMemoryItem(structured_input=si, importance=0.5)
        self.mem.store_working(wm)
        got = self.mem.get_working(limit=10)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0].id, wm.id)

    def test_subtype_preserved_on_load(self):
        si = StructuredInput(raw_text="hi", intent="statement")
        wm = WorkingMemoryItem(structured_input=si, context={"k": 1}, importance=0.5)
        self.mem.store_working(wm)
        got = self.mem.get_working(limit=10)[0]
        self.assertIsInstance(got, WorkingMemoryItem)
        self.assertEqual(got.context, {"k": 1})
        # structured_input is JSON-roundtripped as a plain dict (its
        # fields are typed Any in the dataclass).  The contract only
        # requires preserving the *MemoryItem* concrete subclass.
        self.assertEqual(got.structured_input["raw_text"], "hi")


class TestEpisodicStore(unittest.TestCase):
    def setUp(self):
        self.mem = SQLiteMemorySystem()

    def tearDown(self):
        self.mem.close()

    def test_store_and_get_episodic_round_trip(self):
        si = StructuredInput(raw_text="hi", intent="statement")
        dec = ARIDecision(action_type="execute", payload={"x": 1})
        ep = EpisodicItem(structured_input=si, decision=dec, importance=0.5)
        self.mem.store_episodic(ep)
        got = self.mem.get_episodic(limit=10)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0].id, ep.id)

    def test_subtype_preserved_on_load(self):
        si = StructuredInput(raw_text="hi", intent="statement")
        dec = ARIDecision(action_type="execute", payload={"x": 1})
        ep = EpisodicItem(
            structured_input=si,
            decision=dec,
            outcome="success",
            notes="user happy",
            importance=0.6,
        )
        self.mem.store_episodic(ep)
        got = self.mem.get_episodic(limit=10)[0]
        self.assertIsInstance(got, EpisodicItem)
        self.assertEqual(got.outcome, "success")
        self.assertEqual(got.notes, "user happy")
        # The contract only requires preserving the MemoryItem concrete
        # subclass.  ARIDecision is a typed Any inside EpisodicItem and
        # JSON-roundtrips to a dict – same as simple_memory_system.
        self.assertEqual(got.decision["action_type"], "execute")


class TestSemanticStore(unittest.TestCase):
    def setUp(self):
        self.mem = SQLiteMemorySystem()

    def tearDown(self):
        self.mem.close()

    def test_store_and_get_semantic_round_trip(self):
        sm = SemanticItem(fact="ARIA has memory", importance=0.7)
        self.mem.store_semantic(sm)
        got = self.mem.get_semantic()
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0].id, sm.id)

    def test_subtype_preserved_on_load(self):
        sm = SemanticItem(
            fact="ARIA has memory",
            source_episodic_ids=["e1", "e2"],
            confidence=0.9,
            importance=0.7,
        )
        self.mem.store_semantic(sm)
        got = self.mem.get_semantic()[0]
        self.assertIsInstance(got, SemanticItem)
        self.assertEqual(got.source_episodic_ids, ["e1", "e2"])
        self.assertAlmostEqual(got.confidence, 0.9)

    def test_get_semantic_with_query_substring(self):
        sm1 = SemanticItem(fact="ARIA has memory", importance=0.7)
        sm2 = SemanticItem(fact="ARIA has goals", importance=0.6)
        self.mem.store_semantic(sm1)
        self.mem.store_semantic(sm2)
        out = self.mem.get_semantic(query="memory")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].fact, "ARIA has memory")


class TestImportanceUpdates(unittest.TestCase):
    def setUp(self):
        self.mem = SQLiteMemorySystem()

    def tearDown(self):
        self.mem.close()

    def test_update_importance_clamps_high(self):
        wm = WorkingMemoryItem(importance=0.9)
        self.mem.store_working(wm)
        self.mem.update_importance(wm.id, 5.0)
        loaded = self.mem.get_working(limit=10)[0]
        self.assertAlmostEqual(loaded.importance, 1.0)

    def test_update_importance_clamps_low(self):
        wm = WorkingMemoryItem(importance=0.1)
        self.mem.store_working(wm)
        self.mem.update_importance(wm.id, -10.0)
        loaded = self.mem.get_working(limit=10)[0]
        self.assertAlmostEqual(loaded.importance, 0.0)

    def test_update_importance_unknown_id_is_noop(self):
        self.mem.update_importance("does-not-exist", 0.5)


class TestSizeAndConsolidation(unittest.TestCase):
    def setUp(self):
        self.mem = SQLiteMemorySystem()

    def tearDown(self):
        self.mem.close()

    def test_size_counts_each_store(self):
        self.mem.store_working(WorkingMemoryItem())
        self.mem.store_episodic(EpisodicItem())
        self.mem.store_semantic(SemanticItem(fact="x"))
        s = self.mem.size()
        self.assertEqual(s["working"], 1)
        self.assertEqual(s["episodic"], 1)
        self.assertEqual(s["semantic"], 1)
        self.assertEqual(s["total"], 3)

    def test_consolidate_promotes_high_importance(self):
        # Working item with importance >= threshold should be promoted.
        si = StructuredInput(raw_text="promote me", intent="statement")
        wm = WorkingMemoryItem(structured_input=si, importance=0.9)
        self.mem.store_working(wm)
        promoted = self.mem.consolidate(importance_threshold=0.7)
        self.assertGreaterEqual(promoted, 1)
        # After promotion, working store is empty and semantic has at
        # least one entry.
        self.assertEqual(self.mem.get_working(limit=10), [])
        self.assertGreaterEqual(len(self.mem.get_semantic()), 1)

    def test_forget_low_importance_removes_old_low_items(self):
        import datetime
        si = StructuredInput(raw_text="old", intent="statement")
        # Manually backdate the timestamp by editing the row after store.
        wm = WorkingMemoryItem(structured_input=si, importance=0.05)
        self.mem.store_working(wm)
        old_ts = "2000-01-01T00:00:00"
        with self.mem._conn:
            self.mem._conn.execute(
                "UPDATE memory_items SET timestamp=? WHERE id=?", (old_ts, wm.id)
            )
        removed = self.mem.forget_low_importance(
            threshold=0.2,
            older_than=datetime.timedelta(days=30),
        )
        self.assertGreaterEqual(removed, 1)


class TestFileBackedDB(unittest.TestCase):
    """Same tests, but with a real on-disk DB to prove file persistence."""

    def setUp(self):
        self.path = _temp_db()
        self.mem = SQLiteMemorySystem(self.path)

    def tearDown(self):
        self.mem.close()
        try:
            os.remove(self.path)
        except OSError:
            pass

    def test_restart_preserves_memory(self):
        si = StructuredInput(raw_text="hello", intent="statement")
        ep = EpisodicItem(
            structured_input=si,
            decision=ARIDecision(action_type="inform"),
            importance=0.5,
        )
        self.mem.store_episodic(ep)
        # Close and reopen against the same file.
        self.mem.close()

        mem2 = SQLiteMemorySystem(self.path)
        try:
            got = mem2.get_episodic(limit=10)
            self.assertEqual(len(got), 1)
            self.assertIsInstance(got[0], EpisodicItem)
            self.assertEqual(got[0].id, ep.id)
        finally:
            mem2.close()

    def test_round_trip_50_episodes_preserves_subtypes(self):
        import datetime
        base = datetime.datetime.now()
        for i in range(50):
            si = StructuredInput(raw_text=f"episode {i}", intent="statement")
            ep = EpisodicItem(
                structured_input=si,
                decision=ARIDecision(action_type="inform"),
                importance=0.5,
                timestamp=base + datetime.timedelta(seconds=i),
            )
            self.mem.store_episodic(ep)
        loaded = self.mem.get_episodic(limit=100)
        self.assertEqual(len(loaded), 50)
        for item in loaded:
            self.assertIsInstance(item, EpisodicItem)

    def test_record_outcome_survives_restart(self):
        si = StructuredInput(raw_text="x", intent="statement")
        ep = EpisodicItem(structured_input=si, importance=0.5)
        self.mem.store_episodic(ep)
        self.mem.record_outcome(ep.id, Outcome.SUCCESS)
        self.mem.close()

        mem2 = SQLiteMemorySystem(self.path)
        try:
            loaded = mem2.get_episodic(limit=10)[0]
            self.assertIsInstance(loaded, EpisodicItem)
            self.assertEqual(loaded.outcome, "success")
            self.assertAlmostEqual(loaded.importance, 0.6, places=5)
        finally:
            mem2.close()


if __name__ == "__main__":
    unittest.main()