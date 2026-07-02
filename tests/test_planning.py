from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock
from aria_core.planning import PlanningEngine, Plan, PlanStep
from aria_core.planning.interfaces import PlanStepState


class TestPlanStep:
    def test_pending_is_ready(self):
        s = PlanStep(description="do thing")
        assert s.is_ready is True

    def test_depends_on_not_ready(self):
        s = PlanStep(description="depends", depends_on=["A"])
        assert s.is_ready is False

    def test_can_run_no_deps(self):
        s = PlanStep(description="independent")
        assert s.can_run(set()) is True

    def test_can_run_deps_met(self):
        s = PlanStep(description="depends", depends_on=["A"])
        assert s.can_run({"A"}) is True

    def test_can_run_deps_unmet(self):
        s = PlanStep(description="depends", depends_on=["A"])
        assert s.can_run(set()) is False

    def test_not_ready_if_already_completed(self):
        s = PlanStep(description="done", state=PlanStepState.COMPLETED)
        assert s.can_run(set()) is False


class TestPlan:
    def test_progress_empty(self):
        p = Plan(objective="test")
        assert p.progress == 0.0

    def test_progress_partial(self):
        p = Plan(objective="test")
        p.steps = [
            PlanStep(description="a", state=PlanStepState.COMPLETED),
            PlanStep(description="b", state=PlanStepState.PENDING),
        ]
        assert p.progress == 0.5

    def test_progress_complete(self):
        p = Plan(objective="test")
        p.steps = [
            PlanStep(description="a", state=PlanStepState.COMPLETED),
            PlanStep(description="b", state=PlanStepState.SKIPPED),
        ]
        assert p.is_complete is True

    def test_next_step_respects_deps(self):
        p = Plan(objective="test")
        s1 = PlanStep(description="first")
        s2 = PlanStep(description="second", depends_on=["idx_0"])
        p.steps = [s1, s2]
        assert p.next_step is s1

    def test_next_step_none_when_done(self):
        p = Plan(objective="test")
        p.steps = [PlanStep(description="a", state=PlanStepState.COMPLETED)]
        assert p.next_step is None

    def test_failed_steps(self):
        p = Plan(objective="test")
        p.steps = [
            PlanStep(description="ok", state=PlanStepState.COMPLETED),
            PlanStep(description="bad", state=PlanStepState.FAILED),
        ]
        assert len(p.failed_steps) == 1
        assert p.failed_steps[0].description == "bad"


class TestPlanningEngine:
    def test_create_plan_stub(self):
        engine = PlanningEngine()
        plan = engine.create_plan("review repository")
        assert plan.objective == "review repository"
        assert len(plan.steps) == 1
        assert plan.steps[0].action == "reason"

    def test_create_plan_with_llm(self):
        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = json.dumps([
            {"description": "inspect files", "action": "list_files", "args": {"path": "."}},
            {"description": "read code", "action": "read_file", "args": {"path": "main.py"}, "depends_on": [0]},
        ])
        mock_llm.generate.return_value = mock_resp

        engine = PlanningEngine(llm=mock_llm)
        plan = engine.create_plan("review code quality")
        assert len(plan.steps) == 2
        assert plan.steps[0].action == "list_files"
        assert plan.steps[1].depends_on == ["0"]

    def test_get_plan(self):
        engine = PlanningEngine()
        plan = engine.create_plan("test")
        assert engine.get_plan(plan.id) is plan
        assert engine.get_plan("nonexistent") is None

    def test_list_plans(self):
        engine = PlanningEngine()
        engine.create_plan("plan a")
        engine.create_plan("plan b")
        assert len(engine.list_plans()) == 2

    def test_step_completed(self):
        engine = PlanningEngine()
        plan = engine.create_plan("test")
        step = plan.steps[0]
        engine.step_completed(plan.id, step.id, result="done")
        assert step.state == PlanStepState.COMPLETED
        assert step.result == "done"
        assert plan.completed_at is not None

    def test_step_failed(self):
        engine = PlanningEngine()
        plan = engine.create_plan("test")
        step = plan.steps[0]
        engine.step_failed(plan.id, step.id, reason="error")
        assert step.state == PlanStepState.FAILED
        assert step.result == "error"

    def test_llm_failure_falls_back_to_stub(self):
        mock_llm = MagicMock()
        mock_llm.generate.side_effect = Exception("LLM down")

        engine = PlanningEngine(llm=mock_llm)
        plan = engine.create_plan("anything")
        assert len(plan.steps) == 1
        assert plan.steps[0].action == "reason"

    def test_invalid_json_falls_back(self):
        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "not json at all"
        mock_llm.generate.return_value = mock_resp

        engine = PlanningEngine(llm=mock_llm)
        plan = engine.create_plan("test")
        assert len(plan.steps) == 1

    def test_step_progression(self):
        engine = PlanningEngine()
        plan = engine.create_plan("multi step")
        plan.steps = [
            PlanStep(description="a", action="tool_a"),
            PlanStep(description="b", action="tool_b", depends_on=["_unused"]),
        ]
        # First step should be next
        assert plan.next_step.description == "a"
        # Complete it
        engine.step_completed(plan.id, plan.steps[0].id)
        assert plan.progress == 0.5
