"""
Tests for the SQLite-backed PersistenceProtocol implementation.

Exercises both goal persistence and memory persistence through the
SQLiteGoalStore facade.  Subtype preservation across load is asserted
with isinstance for every concrete MemoryItem subclass.
"""

import os
import tempfile
import unittest

from aria_core.goals import Goal, GoalManager, SQLiteGoalStore
from aria_core.interfaces import ARIDecision, StructuredInput
from aria_core.memory.models import (
    EpisodicItem,
    SemanticItem,
    WorkingMemoryItem,
)


def _temp_db() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)  # let SQLite create it cleanly
    return path


class TestGoalPersistence(unittest.TestCase):
    def setUp(self):
        self.path = _temp_db()
        self.store = SQLiteGoalStore(self.path)

    def tearDown(self):
        self.store.close()
        try:
            os.remove(self.path)
        except OSError:
            pass

    def test_save_and_load_round_trip(self):
        g = Goal(description="learn ARIA", priority=2.5)
        self.store.save_goal(g)
        loaded = self.store.load_all_goals()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].id, g.id)
        self.assertEqual(loaded[0].description, "learn ARIA")
        self.assertAlmostEqual(loaded[0].priority, 2.5)
        self.assertEqual(loaded[0].metadata, {})

    def test_save_preserves_deadline_and_metadata(self):
        import datetime
        deadline = datetime.datetime(2026, 12, 31, 23, 59, 59)
        g = Goal(
            description="ship M2",
            priority=3.0,
            deadline=deadline,
            metadata={"owner": "mimo", "tags": ["urgent", "milestone"]},
        )
        self.store.save_goal(g)
        loaded = self.store.load_all_goals()[0]
        self.assertEqual(loaded.deadline, deadline)
        self.assertEqual(loaded.metadata, g.metadata)

    def test_delete_unknown_id_is_noop(self):
        # Must not raise.
        self.store.delete_goal("does-not-exist")

    def test_delete_removes_goal(self):
        g = Goal(description="x", priority=1.0)
        self.store.save_goal(g)
        self.store.delete_goal(g.id)
        self.assertEqual(self.store.load_all_goals(), [])

    def test_save_is_idempotent_on_existing_id(self):
        g = Goal(description="original", priority=1.0)
        self.store.save_goal(g)
        # Same id, different content → upsert overwrites.
        g2 = Goal(id=g.id, description="updated", priority=2.0)
        self.store.save_goal(g2)
        loaded = self.store.load_all_goals()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].description, "updated")


class TestGoalManagerWithPersistence(unittest.TestCase):
    def setUp(self):
        self.path = _temp_db()
        self.store = SQLiteGoalStore(self.path)

    def tearDown(self):
        self.store.close()
        try:
            os.remove(self.path)
        except OSError:
            pass

    def test_manager_hydrates_from_persistence(self):
        # Persist a goal directly via the backend, then construct a
        # manager that has no in-memory seed list.  The manager must
        # load the goal from disk.
        g = Goal(description="learn ARIA", priority=2.5)
        self.store.save_goal(g)

        m = GoalManager(persistence=self.store)
        self.assertEqual(len(m.list_goals()), 1)
        self.assertEqual(m.list_goals()[0].id, g.id)

    def test_add_goal_mirrors_to_backend(self):
        m = GoalManager(persistence=self.store)
        g = Goal(description="x", priority=1.0)
        m.add_goal(g)
        # Backend should know about it too.
        self.assertEqual(len(self.store.load_all_goals()), 1)

    def test_remove_goal_mirrors_to_backend(self):
        m = GoalManager(persistence=self.store)
        g = Goal(description="x", priority=1.0)
        m.add_goal(g)
        m.remove_goal(g.id)
        self.assertEqual(self.store.load_all_goals(), [])

    def test_simulation_of_restart_preserves_goals(self):
        # Simulate the M2 demo: kill the process mid-session, restart,
        # ask ARIA about the goals.
        m1 = GoalManager(persistence=self.store)
        m1.add_goal(Goal(description="learn ARIA", priority=2.0))
        m1.add_goal(Goal(description="ship M3", priority=1.5))

        # "Restart" – drop m1, build a fresh manager against the same DB.
        m2 = GoalManager(persistence=self.store)
        goals = m2.list_goals()
        self.assertEqual(len(goals), 2)
        descriptions = {g.description for g in goals}
        self.assertEqual(descriptions, {"learn ARIA", "ship M3"})

    def test_relevant_goals_works_with_persistence(self):
        m = GoalManager(persistence=self.store)
        m.add_goal(Goal(description="Learn Spanish", priority=2.0))
        m.add_goal(Goal(description="Stay healthy", priority=1.0))
        relevant = m.relevant_goals("spanish")
        self.assertEqual(len(relevant), 1)
        self.assertEqual(relevant[0].description, "Learn Spanish")

    def test_manager_without_persistence_still_works(self):
        # Backward-compat: the original API must remain functional.
        m = GoalManager()
        m.add_goal(Goal(description="x", priority=1.0))
        self.assertEqual(len(m.list_goals()), 1)


class TestMemoryPersistenceThroughGoalStore(unittest.TestCase):
    """SQLiteGoalStore implements the full PersistenceProtocol, so it
    can also round-trip memory items via delegation to SQLiteMemorySystem."""

    def setUp(self):
        self.path = _temp_db()
        self.store = SQLiteGoalStore(self.path)

    def tearDown(self):
        self.store.close()
        try:
            os.remove(self.path)
        except OSError:
            pass

    def test_save_and_load_memory_items_preserves_subtypes(self):
        si = StructuredInput(raw_text="hello", intent="statement")
        wm = WorkingMemoryItem(structured_input=si, importance=0.4)
        em = EpisodicItem(
            structured_input=si,
            decision=ARIDecision(action_type="inform"),
            outcome=None,
            importance=0.5,
        )
        sm = SemanticItem(fact="ARIA has memory", importance=0.6)
        self.store.save_memory_items([wm, em, sm])

        loaded_wm = self.store.load_memory_items(store="working")
        loaded_em = self.store.load_memory_items(store="episodic")
        loaded_sm = self.store.load_memory_items(store="semantic")

        self.assertEqual(len(loaded_wm), 1)
        self.assertIsInstance(loaded_wm[0], WorkingMemoryItem)
        self.assertEqual(loaded_wm[0].id, wm.id)

        self.assertEqual(len(loaded_em), 1)
        self.assertIsInstance(loaded_em[0], EpisodicItem)
        self.assertEqual(loaded_em[0].id, em.id)

        self.assertEqual(len(loaded_sm), 1)
        self.assertIsInstance(loaded_sm[0], SemanticItem)
        self.assertEqual(loaded_sm[0].id, sm.id)
        # Round-tripped SemanticItem fact should equal the original.
        self.assertEqual(loaded_sm[0].fact, "ARIA has memory")

    def test_update_memory_importance_clamps_and_persists(self):
        sm = SemanticItem(fact="x", importance=0.5)
        self.store.save_memory_items([sm])
        # Push past the upper bound.
        self.store.update_memory_importance(sm.id, 5.0)
        loaded = self.store.load_memory_items(store="semantic")
        self.assertAlmostEqual(loaded[0].importance, 1.0)

        # Pull below zero.
        self.store.update_memory_importance(sm.id, -10.0)
        loaded = self.store.load_memory_items(store="semantic")
        self.assertAlmostEqual(loaded[0].importance, 0.0)

    def test_update_memory_importance_unknown_id_is_noop(self):
        # Must not raise.
        self.store.update_memory_importance("does-not-exist", 0.5)

    def test_load_memory_items_unknown_store_raises(self):
        with self.assertRaises(ValueError):
            self.store.load_memory_items(store="nope")  # type: ignore[arg-type]


class TestPersistenceProtocolRuntimeCheckable(unittest.TestCase):
    def test_sqlite_store_satisfies_protocol(self):
        from aria_core.persistence.interfaces import PersistenceProtocol
        path = _temp_db()
        store = SQLiteGoalStore(path)
        try:
            self.assertIsInstance(store, PersistenceProtocol)
        finally:
            store.close()
            try:
                os.remove(path)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()