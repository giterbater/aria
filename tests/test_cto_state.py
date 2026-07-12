from __future__ import annotations

import pytest
from cto.state import CycleState


class TestCycleState:
    def test_defaults(self):
        state = CycleState()
        assert state.cycle_id
        assert state.phase == "inspect"
        assert state.actions_taken == []
        assert state.files_modified == []
        assert state.tests_passed is None
        assert state.commit_sha is None
        assert state.error is None

    def test_record_action(self):
        state = CycleState()
        new_state = state.record_action({"tool": "edit", "success": True})
        assert len(new_state.actions_taken) == 1
        assert new_state.actions_taken[0]["tool"] == "edit"
        assert len(state.actions_taken) == 0  # original unchanged

    def test_set_files_modified(self):
        state = CycleState()
        new_state = state.set_files_modified(["a.py", "b.py"])
        assert new_state.files_modified == ["a.py", "b.py"]

    def test_set_phase(self):
        state = CycleState()
        new_state = state.set_phase("execute")
        assert new_state.phase == "execute"

    def test_set_error(self):
        state = CycleState()
        new_state = state.set_error("something broke")
        assert new_state.error == "something broke"

    def test_set_commit(self):
        state = CycleState()
        new_state = state.set_commit("abc123")
        assert new_state.commit_sha == "abc123"

    def test_to_dict(self):
        state = CycleState()
        d = state.to_dict()
        assert "cycle_id" in d
        assert "started_at" in d
        assert "phase" in d
        assert "actions_taken" in d

    def test_immutable(self):
        state = CycleState()
        with pytest.raises(AttributeError):
            state.phase = "other"
