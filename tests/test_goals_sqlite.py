"""
Tests for the SQLiteGoalStore used through GoalManager(persistence=...).

Round-trips goals and metadata, verifies hydration after restart, and
confirms the existing in-memory API still works.
"""

import datetime
import os
import tempfile
import unittest

from aria_core.goals import Goal, GoalManager, SQLiteGoalStore


def _temp_db() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    return path


class TestSQLiteGoalStore(unittest.TestCase):
    def setUp(self):
        self.path = _temp_db()
        self.store = SQLiteGoalStore(self.path)

    def tearDown(self):
        self.store.close()
        try:
            os.remove(self.path)
        except OSError:
            pass

    def test_initialize_is_idempotent(self):
        # Calling initialize twice must not raise.
        self.store.initialize()
        self.store.initialize()

    def test_save_and_load_round_trip(self):
        deadline = datetime.datetime(2026, 12, 31)
        g = Goal(
            description="ship M2",
            priority=3.0,
            deadline=deadline,
            metadata={"tags": ["milestone"]},
        )
        self.store.save_goal(g)
        loaded = self.store.load_all_goals()
        self.assertEqual(len(loaded), 1)
        out = loaded[0]
        self.assertEqual(out.id, g.id)
        self.assertEqual(out.description, "ship M2")
        self.assertAlmostEqual(out.priority, 3.0)
        self.assertEqual(out.deadline, deadline)
        self.assertEqual(out.metadata, {"tags": ["milestone"]})

    def test_load_all_goals_returns_empty_list_initially(self):
        self.assertEqual(self.store.load_all_goals(), [])

    def test_delete_goal_unknown_id_is_noop(self):
        self.store.delete_goal("does-not-exist")
        self.assertEqual(self.store.load_all_goals(), [])

    def test_delete_goal_removes_from_load(self):
        g = Goal(description="x", priority=1.0)
        self.store.save_goal(g)
        self.store.delete_goal(g.id)
        self.assertEqual(self.store.load_all_goals(), [])

    def test_save_is_upsert(self):
        g = Goal(description="first", priority=1.0)
        self.store.save_goal(g)
        # Same id, different content.
        self.store.save_goal(Goal(id=g.id, description="updated", priority=2.0))
        loaded = self.store.load_all_goals()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].description, "updated")
        self.assertAlmostEqual(loaded[0].priority, 2.0)

    def test_save_preserves_no_deadline(self):
        g = Goal(description="ongoing", priority=1.0, deadline=None)
        self.store.save_goal(g)
        loaded = self.store.load_all_goals()[0]
        self.assertIsNone(loaded.deadline)

    def test_metadata_with_non_serializable_is_handled(self):
        # JSON cannot encode sets; the store should still not crash for
        # serializable metadata (sets aren't supported, but the manager
        # passes dicts).
        g = Goal(description="x", metadata={"k": [1, 2, 3], "n": 4})
        self.store.save_goal(g)
        loaded = self.store.load_all_goals()[0]
        self.assertEqual(loaded.metadata, {"k": [1, 2, 3], "n": 4})


class TestGoalManagerWithSQLite(unittest.TestCase):
    def setUp(self):
        self.path = _temp_db()
        self.store = SQLiteGoalStore(self.path)

    def tearDown(self):
        self.store.close()
        try:
            os.remove(self.path)
        except OSError:
            pass

    def test_add_and_list_goals_persisted(self):
        m = GoalManager(persistence=self.store)
        m.add_goal(Goal(description="a", priority=1.0))
        m.add_goal(Goal(description="b", priority=2.0))
        self.assertEqual(len(m.list_goals()), 2)
        # Backend should also know about both goals.
        self.assertEqual(len(self.store.load_all_goals()), 2)

    def test_remove_goal_persisted(self):
        m = GoalManager(persistence=self.store)
        g = Goal(description="x", priority=1.0)
        m.add_goal(g)
        m.remove_goal(g.id)
        self.assertEqual(m.list_goals(), [])
        self.assertEqual(self.store.load_all_goals(), [])

    def test_relevant_goals_returns_persisted_goals(self):
        m = GoalManager(persistence=self.store)
        m.add_goal(Goal(description="Learn ARIA", priority=2.0))
        m.add_goal(Goal(description="Learn Spanish", priority=1.0))
        relevant = m.relevant_goals("ARIA")
        self.assertEqual(len(relevant), 1)
        self.assertEqual(relevant[0].description, "Learn ARIA")

    def test_restart_preserves_goals(self):
        m1 = GoalManager(persistence=self.store)
        m1.add_goal(Goal(description="learn ARIA", priority=2.0))
        m1.add_goal(Goal(description="ship M3", priority=1.5))

        # "Restart" – fresh manager against the same DB.
        m2 = GoalManager(persistence=self.store)
        descriptions = {g.description for g in m2.list_goals()}
        self.assertEqual(descriptions, {"learn ARIA", "ship M3"})

    def test_caller_supplied_goals_added_on_top(self):
        # If the caller passes initial goals in addition to a backend,
        # the manager should persist them too (so a second process
        # sees them).
        seed = Goal(description="seed", priority=1.0)
        m = GoalManager(goals=[seed], persistence=self.store)
        self.assertEqual(len(m.list_goals()), 1)
        # Hydrate again from the same DB.
        m2 = GoalManager(persistence=self.store)
        self.assertEqual(len(m2.list_goals()), 1)
        self.assertEqual(m2.list_goals()[0].id, seed.id)

    def test_no_persistence_kwarg_works(self):
        # Backwards-compat with the pre-M2 API.
        m = GoalManager()
        m.add_goal(Goal(description="x", priority=1.0))
        self.assertEqual(len(m.list_goals()), 1)


class TestSQLiteGoalStoreRealFile(unittest.TestCase):
    """Round-trip a goal against a real file – proves persistence to disk."""

    def setUp(self):
        self.path = _temp_db()

    def tearDown(self):
        try:
            os.remove(self.path)
        except OSError:
            pass

    def test_round_trip_after_close_and_reopen(self):
        store1 = SQLiteGoalStore(self.path)
        g = Goal(description="durable", priority=2.0)
        store1.save_goal(g)
        store1.close()

        store2 = SQLiteGoalStore(self.path)
        try:
            loaded = store2.load_all_goals()
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].description, "durable")
            self.assertEqual(loaded[0].id, g.id)
        finally:
            store2.close()


if __name__ == "__main__":
    unittest.main()