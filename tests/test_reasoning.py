from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock
from aria_core.reasoning import ReasoningEngine, ReasoningContext, ReasonedPlan, ConfidenceScore


class TestConfidenceScore:
    def test_overall(self):
        c = ConfidenceScore(goal=0.9, plan=0.8, skill_selection=0.7, memory_match=0.6)
        assert c.overall == pytest.approx(0.75)

    def test_is_confident(self):
        c = ConfidenceScore(goal=0.9, plan=0.8, skill_selection=0.7, memory_match=0.6)
        assert c.is_confident is True

    def test_not_confident(self):
        c = ConfidenceScore(goal=0.3, plan=0.2, skill_selection=0.4, memory_match=0.1)
        assert c.is_confident is False

    def test_summary(self):
        c = ConfidenceScore(goal=0.9, plan=0.8, skill_selection=0.7, memory_match=0.6)
        s = c.summary()
        assert "Goal: 90%" in s
        assert "Overall: 75%" in s


class TestReasoningContext:
    def test_defaults(self):
        ctx = ReasoningContext()
        assert ctx.objective == ""
        assert ctx.available_skills == []
        assert ctx.constraints == []


class TestReasoningEngineFallback:
    def test_fallback_read(self):
        engine = ReasoningEngine()
        plan = engine.reason("read the codebase")
        assert len(plan.steps) >= 1
        assert plan.steps[0]["skill"] == "code"
        assert plan.steps[0]["action"] == "scan"

    def test_fallback_analyze(self):
        engine = ReasoningEngine()
        plan = engine.reason("analyze code complexity")
        assert len(plan.steps) >= 1
        actions = {s["action"] for s in plan.steps}
        assert "complexity" in actions or "scan" in actions

    def test_fallback_test(self):
        engine = ReasoningEngine()
        plan = engine.reason("run the test suite")
        assert len(plan.steps) >= 1
        assert any(s["skill"] == "terminal" for s in plan.steps)

    def test_fallback_git(self):
        engine = ReasoningEngine()
        plan = engine.reason("check git status")
        assert len(plan.steps) >= 1
        assert any(s["skill"] == "git" for s in plan.steps)

    def test_fallback_todo(self):
        engine = ReasoningEngine()
        plan = engine.reason("find all TODO comments")
        assert len(plan.steps) >= 1
        assert any(s["action"] == "find_patterns" for s in plan.steps)

    def test_fallback_unknown(self):
        engine = ReasoningEngine()
        plan = engine.reason("do something random")
        assert len(plan.steps) >= 1

    def test_confidence(self):
        engine = ReasoningEngine()
        plan = engine.reason("analyze code")
        assert plan.confidence.overall > 0
        assert plan.confidence.plan > 0

    def test_fallback_no_steps(self):
        engine = ReasoningEngine()
        plan = engine.reason("")
        assert len(plan.steps) >= 1


class TestReasoningEngineWithLLM:
    def test_reason_with_llm(self):
        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = json.dumps({
            "goal": "analyze codebase",
            "steps": [
                {"id": 1, "skill": "code", "action": "scan", "args": {"path": "."},
                 "description": "Scan repo", "dependencies": [], "confidence": 0.9, "risk": "low"},
                {"id": 2, "skill": "code", "action": "complexity", "args": {"path": "."},
                 "description": "Analyze complexity", "dependencies": [1], "confidence": 0.85, "risk": "low"},
            ],
            "overall_confidence": 0.88,
            "risks": ["large codebase"],
            "alternatives": ["manual review"],
            "reasoning": "Two-step analysis approach",
        })
        mock_llm.generate.return_value = mock_resp

        engine = ReasoningEngine(llm=mock_llm)
        plan = engine.reason("analyze codebase")
        assert len(plan.steps) == 2
        assert plan.confidence.plan == 0.88
        assert plan.reasoning == "Two-step analysis approach"
        assert len(plan.risks) == 1

    def test_llm_failure_falls_back(self):
        mock_llm = MagicMock()
        mock_llm.generate.side_effect = Exception("LLM down")

        engine = ReasoningEngine(llm=mock_llm)
        plan = engine.reason("analyze code")
        assert len(plan.steps) >= 1

    def test_verify_plan(self):
        engine = ReasoningEngine()
        plan = ReasonedPlan(
            steps=[
                {"id": 1, "skill": "code", "confidence": 0.9},
                {"id": 2, "skill": "unknown_skill", "confidence": 0.8, "dependencies": [1]},
            ]
        )
        verified = engine._verify_plan(plan)
        assert verified.verified is False
        assert any("Unknown skills" in n for n in verified.verification_notes)

    def test_verify_circular_deps(self):
        engine = ReasoningEngine()
        plan = ReasonedPlan(
            steps=[
                {"id": 1, "skill": "code", "dependencies": [2]},
                {"id": 2, "skill": "code", "dependencies": [1]},
            ]
        )
        verified = engine._verify_plan(plan)
        assert verified.verified is False
        assert any("Circular" in n for n in verified.verification_notes)

    def test_verify_clean_plan(self):
        engine = ReasoningEngine()
        plan = ReasonedPlan(
            steps=[
                {"id": 1, "skill": "code", "confidence": 0.9},
                {"id": 2, "skill": "terminal", "confidence": 0.8, "dependencies": [1]},
            ]
        )
        verified = engine._verify_plan(plan, available_skills=["code", "terminal", "git"])
        assert verified.verified is True


class TestReplanFromFailure:
    def test_replan_removes_failed(self):
        engine = ReasoningEngine()
        original = ReasonedPlan(
            steps=[
                {"id": 1, "skill": "code", "status": "completed"},
                {"id": 2, "skill": "terminal", "status": "failed"},
                {"id": 3, "skill": "git", "dependencies": [2]},
            ]
        )
        failed = {"id": 2, "skill": "terminal"}
        replan = engine.replan_from_failure(original, failed, "command failed")
        assert len(replan.steps) == 1
        assert replan.steps[0]["id"] == 3

    def test_replan_clears_resolved_deps(self):
        engine = ReasoningEngine()
        original = ReasonedPlan(
            steps=[
                {"id": 1, "skill": "code", "status": "completed"},
                {"id": 2, "skill": "terminal", "status": "failed"},
                {"id": 3, "skill": "git", "dependencies": [1, 2]},
            ]
        )
        failed = {"id": 2, "skill": "terminal"}
        replan = engine.replan_from_failure(original, failed, "fail")
        assert replan.steps[0]["dependencies"] == [1]
