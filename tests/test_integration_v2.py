from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock
from aria_core.integration import ARIACore
from aria_core.skills.builtin import FileSkill, TerminalSkill, GitSkill
from aria_core.skills.builtin.code_skill import CodeSkill
from aria_core.goals import GoalState


class TestARIACoreInit:
    def test_init(self, tmp_path):
        core = ARIACore(db_path=str(tmp_path / "test.db"))
        assert core.goals is not None
        assert core.planning is not None
        assert core.reflection is not None
        assert core.knowledge is not None
        assert core.learning is not None
        assert core.skills is not None
        core.shutdown()

    def test_init_with_llm(self, tmp_path):
        mock_llm = MagicMock()
        core = ARIACore(llm=mock_llm, db_path=str(tmp_path / "test.db"))
        assert core._llm is mock_llm
        core.shutdown()


class TestARIACoreProcessObjective:
    def test_process_simple_objective(self, tmp_path):
        core = ARIACore(db_path=str(tmp_path / "test.db"))
        core.skills.register(FileSkill(base_path=str(tmp_path)))

        summary = core.process_objective("Create a file called test.txt")
        assert "success" in summary
        assert "plan_steps" in summary
        assert summary["plan_steps"] >= 1
        core.shutdown()

    def test_process_with_skills(self, tmp_path):
        core = ARIACore(db_path=str(tmp_path / "test.db"))
        core.skills.register(FileSkill(base_path=str(tmp_path)))
        core.skills.register(TerminalSkill())

        summary = core.process_objective("Read a file")
        assert summary["plan_steps"] >= 1
        core.shutdown()

    def test_goal_created(self, tmp_path):
        core = ARIACore(db_path=str(tmp_path / "test.db"))
        core.process_objective("test objective")
        active = core.goals.list_goals(GoalState.ACTIVE)
        completed = core.goals.list_goals(GoalState.COMPLETED)
        assert len(active) + len(completed) >= 1
        core.shutdown()

    def test_plan_created(self, tmp_path):
        core = ARIACore(db_path=str(tmp_path / "test.db"))
        summary = core.process_objective("analyze code")
        assert summary["plan_steps"] >= 1
        core.shutdown()

    def test_reflection_recorded(self, tmp_path):
        core = ARIACore(db_path=str(tmp_path / "test.db"))
        core.process_objective("do something")
        reflections = core.reflection.get_reflections()
        assert len(reflections) >= 1
        core.shutdown()

    def test_knowledge_learned(self, tmp_path):
        core = ARIACore(db_path=str(tmp_path / "test.db"))
        core.process_objective("learn from this")
        assert core.knowledge.count() >= 0
        core.shutdown()


class TestARIACoreStatus:
    def test_status(self, tmp_path):
        core = ARIACore(db_path=str(tmp_path / "test.db"))
        core.skills.register(FileSkill())
        core.skills.register(TerminalSkill())

        status = core.get_status()
        assert "cycle_count" in status
        assert "goals" in status
        assert "knowledge" in status
        assert "skills" in status
        assert "reflection" in status
        assert "tasks" in status
        assert status["skills"]["registered"] == 2
        core.shutdown()


class TestARIACoreLearning:
    def test_learning_accumulates(self, tmp_path):
        core = ARIACore(db_path=str(tmp_path / "test.db"))
        core.process_objective("first task")
        core.process_objective("second task")
        reflections = core.reflection.get_reflections()
        assert len(reflections) >= 2
        core.shutdown()

    def test_workflow_recorded(self, tmp_path):
        core = ARIACore(db_path=str(tmp_path / "test.db"))
        core.process_objective("workflow test")
        workflows = core.learning.get_workflows()
        assert len(workflows) >= 1
        core.shutdown()


class TestARIACoreShutdown:
    def test_shutdown_cleans_up(self, tmp_path):
        core = ARIACore(db_path=str(tmp_path / "test.db"))
        core.process_objective("test")
        core.shutdown()
        # Should not raise
