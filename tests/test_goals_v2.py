from __future__ import annotations

import pytest
from aria_core.goals import Goal, GoalManager, GoalState, Subtask, SQLiteGoalStore


class TestSubtask:
    def test_creation(self):
        s = Subtask(description="do thing")
        assert s.state == GoalState.ACTIVE
        assert s.depends_on == []

    def test_ready_no_deps(self):
        s = Subtask(description="independent")
        assert s.is_ready(set()) is True

    def test_ready_with_deps_met(self):
        s = Subtask(description="depends on A", depends_on=["A"])
        assert s.is_ready({"A"}) is True

    def test_ready_with_deps_unmet(self):
        s = Subtask(description="depends on A", depends_on=["A"])
        assert s.is_ready(set()) is False


class TestGoalProgress:
    def test_no_subtasks_incomplete(self):
        g = Goal(description="simple goal")
        assert g.progress == 0.0

    def test_no_subtasks_complete(self):
        g = Goal(description="done", state=GoalState.COMPLETED)
        assert g.progress == 1.0

    def test_partial_progress(self):
        g = Goal(description="wip")
        g.subtasks = [
            Subtask(description="a", state=GoalState.COMPLETED),
            Subtask(description="b", state=GoalState.ACTIVE),
            Subtask(description="c", state=GoalState.ACTIVE),
        ]
        assert g.progress == pytest.approx(1 / 3)

    def test_full_progress(self):
        g = Goal(description="all done")
        g.subtasks = [
            Subtask(description="a", state=GoalState.COMPLETED),
            Subtask(description="b", state=GoalState.COMPLETED),
        ]
        assert g.progress == 1.0

    def test_next_subtask_respects_deps(self):
        g = Goal(description="ordered")
        s1 = Subtask(description="first", priority=2.0)
        s2 = Subtask(description="second", depends_on=[s1.id], priority=1.0)
        g.subtasks = [s1, s2]
        assert g.next_subtask is s1

    def test_next_subtask_skips_blocked(self):
        g = Goal(description="with blocked")
        s1 = Subtask(description="blocked", state=GoalState.BLOCKED)
        s2 = Subtask(description="ready")
        g.subtasks = [s1, s2]
        assert g.next_subtask is s2

    def test_next_subtask_none_when_all_done(self):
        g = Goal(description="done")
        g.subtasks = [Subtask(description="a", state=GoalState.COMPLETED)]
        assert g.next_subtask is None


class TestGoalManagerV2:
    def test_get_goal(self):
        gm = GoalManager()
        g = Goal(description="test")
        gm.add_goal(g)
        assert gm.get_goal(g.id) is g

    def test_get_goal_not_found(self):
        gm = GoalManager()
        assert gm.get_goal("nonexistent") is None

    def test_list_goals_by_state(self):
        gm = GoalManager()
        g1 = Goal(description="active")
        g2 = Goal(description="done", state=GoalState.COMPLETED)
        gm.add_goal(g1)
        gm.add_goal(g2)
        assert len(gm.list_goals(GoalState.ACTIVE)) == 1
        assert len(gm.list_goals(GoalState.COMPLETED)) == 1
        assert len(gm.list_goals()) == 2

    def test_complete_goal(self):
        gm = GoalManager()
        g = Goal(description="finish me")
        gm.add_goal(g)
        gm.complete_goal(g.id)
        assert g.state == GoalState.COMPLETED
        assert g.completed_at is not None

    def test_block_and_resume(self):
        gm = GoalManager()
        g = Goal(description="blocked")
        gm.add_goal(g)
        gm.block_goal(g.id, "waiting on API")
        assert g.state == GoalState.BLOCKED
        assert g.metadata["block_reason"] == "waiting on API"
        gm.resume_goal(g.id)
        assert g.state == GoalState.ACTIVE

    def test_abandon(self):
        gm = GoalManager()
        g = Goal(description="放弃")
        gm.add_goal(g)
        gm.abandon_goal(g.id, "no longer needed")
        assert g.state == GoalState.ABANDONED

    def test_add_and_complete_subtask(self):
        gm = GoalManager()
        g = Goal(description="with steps")
        s = Subtask(description="step 1")
        gm.add_goal(g)
        gm.add_subtask(g.id, s)
        assert len(g.subtasks) == 1
        gm.complete_subtask(g.id, s.id, result="done")
        assert s.state == GoalState.COMPLETED
        assert s.result == "done"

    def test_fail_subtask(self):
        gm = GoalManager()
        g = Goal(description="with steps")
        s = Subtask(description="step 1")
        gm.add_goal(g)
        gm.add_subtask(g.id, s)
        gm.fail_subtask(g.id, s.id, reason="error")
        assert s.state == GoalState.BLOCKED
        assert s.result == "error"

    def test_auto_complete_goal_when_all_subtasks_done(self):
        gm = GoalManager()
        g = Goal(description="auto complete")
        s1 = Subtask(description="a")
        s2 = Subtask(description="b")
        gm.add_goal(g)
        gm.add_subtask(g.id, s1)
        gm.add_subtask(g.id, s2)
        gm.complete_subtask(g.id, s1.id)
        gm.complete_subtask(g.id, s2.id)
        assert g.state == GoalState.COMPLETED

    def test_overall_progress(self):
        gm = GoalManager()
        g1 = Goal(description="half", priority=1.0)
        g1.subtasks = [Subtask(description="a", state=GoalState.COMPLETED), Subtask(description="b")]
        g2 = Goal(description="done", priority=1.0, state=GoalState.COMPLETED)
        gm.add_goal(g1)
        gm.add_goal(g2)
        # Only active goals counted: g1 has 50% progress
        assert gm.overall_progress() == pytest.approx(0.5)

    def test_next_action(self):
        gm = GoalManager()
        g = Goal(description="task", priority=2.0)
        s = Subtask(description="do this", priority=1.0)
        gm.add_goal(g)
        gm.add_subtask(g.id, s)
        result = gm.next_action()
        assert result is not None
        goal, subtask = result
        assert goal.id == g.id
        assert subtask.id == s.id

    def test_relevant_excludes_completed(self):
        gm = GoalManager()
        g = Goal(description="test goal", state=GoalState.COMPLETED)
        gm.add_goal(g)
        assert gm.relevant_goals("test goal") == []


class TestSQLiteGoalStoreV2:
    def test_subtasks_persist(self, tmp_path):
        db = tmp_path / "test.db"
        store = SQLiteGoalStore(str(db))
        g = Goal(description="with subtasks")
        s1 = Subtask(description="step 1", priority=2.0)
        s2 = Subtask(description="step 2", depends_on=[s1.id])
        g.subtasks = [s1, s2]
        store.save_goal(g)
        loaded = store.load_all_goals()
        store.close()
        assert len(loaded) == 1
        assert len(loaded[0].subtasks) == 2
        assert loaded[0].subtasks[0].description == "step 1"
        assert loaded[0].subtasks[1].depends_on == [s1.id]

    def test_goal_state_persists(self, tmp_path):
        db = tmp_path / "test.db"
        store = SQLiteGoalStore(str(db))
        g = Goal(description="state test", state=GoalState.BLOCKED)
        g.metadata["block_reason"] = "waiting"
        store.save_goal(g)
        loaded = store.load_all_goals()
        store.close()
        assert loaded[0].state == GoalState.BLOCKED
        assert loaded[0].metadata["block_reason"] == "waiting"

    def test_timestamps_persist(self, tmp_path):
        db = tmp_path / "test.db"
        store = SQLiteGoalStore(str(db))
        g = Goal(description="timestamps")
        store.save_goal(g)
        loaded = store.load_all_goals()
        store.close()
        assert loaded[0].created_at is not None
        assert loaded[0].updated_at is not None
