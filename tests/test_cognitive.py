from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock
from aria_core.cognitive import (
    InternalState, CognitiveState, NeedSystem, Need,
    DecisionBias, CognitiveEngine, CognitiveMetrics,
)
from aria_core.cognitive.metrics import MetricsTracker
from aria_core.reasoning import ReasoningEngine, ReasoningContext


# ── CognitiveState ───────────────────────────────────────────────

class TestCognitiveState:
    def test_defaults(self):
        s = CognitiveState()
        assert s.confidence == 0.7
        assert s.frustration == 0.0
        assert s.cycle_count == 0

    def test_to_dict(self):
        s = CognitiveState()
        d = s.to_dict()
        assert "confidence" in d
        assert "curiosity" in d
        assert d["cycle_count"] == 0

    def test_summary(self):
        s = CognitiveState()
        text = s.summary()
        assert "Confidence" in text
        assert "Frustration" in text


# ── InternalState ────────────────────────────────────────────────

class TestInternalState:
    def test_initial_state(self, tmp_path):
        state = InternalState(str(tmp_path / "test.db"))
        assert state.state.confidence == 0.7
        state.close()

    def test_update_success(self, tmp_path):
        state = InternalState(str(tmp_path / "test.db"))
        old_conf = state.state.confidence
        old_frust = state.state.frustration
        state.update_from_outcome(True)
        assert state.state.confidence > old_conf
        assert state.state.frustration <= old_frust
        assert state.state.total_successes == 1
        assert state.state.consecutive_successes == 1
        state.close()

    def test_update_failure(self, tmp_path):
        state = InternalState(str(tmp_path / "test.db"))
        old_conf = state.state.confidence
        old_frust = state.state.frustration
        state.update_from_outcome(False)
        assert state.state.confidence < old_conf
        assert state.state.frustration > old_frust
        assert state.state.total_failures == 1
        assert state.state.consecutive_failures == 1
        state.close()

    def test_consecutive_failures_increase_caution(self, tmp_path):
        state = InternalState(str(tmp_path / "test.db"))
        old_caution = state.state.caution
        for _ in range(4):
            state.update_from_outcome(False)
        assert state.state.caution > old_caution
        assert state.state.consecutive_failures == 4
        state.close()

    def test_novelty_increases_with_novel_context(self, tmp_path):
        state = InternalState(str(tmp_path / "test.db"))
        old_novelty = state.state.novelty
        state.update_from_outcome(True, context={"is_novel": True})
        assert state.state.novelty > old_novelty
        state.close()

    def test_curiosity_increases_with_unknowns(self, tmp_path):
        state = InternalState(str(tmp_path / "test.db"))
        old_curiosity = state.state.curiosity
        state.update_from_outcome(False, context={"unknown_concepts": 3})
        assert state.state.curiosity > old_curiosity
        state.close()

    def test_persistence_resets_after_success_streak(self, tmp_path):
        state = InternalState(str(tmp_path / "test.db"))
        for _ in range(5):
            state.update_from_outcome(False)
        old_frust = state.state.frustration
        for _ in range(6):
            state.update_from_outcome(True)
        state.reset_after_success_streak(threshold=5)
        assert state.state.frustration < old_frust
        state.close()

    def test_persistence_across_sessions(self, tmp_path):
        db = str(tmp_path / "test.db")
        s1 = InternalState(db)
        s1.update_from_outcome(True)
        s1.close()

        s2 = InternalState(db)
        assert s2.state.total_successes == 1
        assert s2.state.cycle_count == 1
        s2.close()

    def test_update_from_reflection(self, tmp_path):
        state = InternalState(str(tmp_path / "test.db"))
        old_conf = state.state.confidence
        state.update_from_reflection("success", 2)
        assert state.state.confidence > old_conf
        state.close()


# ── NeedSystem ───────────────────────────────────────────────────

class TestNeedSystem:
    def test_computes_needs(self):
        ns = NeedSystem()
        state = CognitiveState(curiosity=0.9, novelty=0.8)
        needs = ns.compute(state)
        assert len(needs) > 0
        names = {n.name for n in needs}
        assert "information" in names

    def test_high_frustration_gives_simplicity(self):
        ns = NeedSystem()
        state = CognitiveState(frustration=0.9, persistence=0.2)
        needs = ns.compute(state)
        names = {n.name for n in needs}
        assert "simplicity" in names

    def test_consecutive_failures_give_recovery(self):
        ns = NeedSystem()
        state = CognitiveState(consecutive_failures=3)
        needs = ns.compute(state)
        names = {n.name for n in needs}
        assert "recovery" in names

    def test_strongest_need(self):
        ns = NeedSystem()
        state = CognitiveState(curiosity=0.9, confidence=0.9, persistence=0.9)
        need = ns.get_strongest_need(state)
        assert need is not None
        assert need.strength > 0

    def test_no_needs_when_balanced(self):
        ns = NeedSystem()
        state = CognitiveState(curiosity=0.3, frustration=0.1, confidence=0.7)
        needs = ns.compute(state)
        # May still have some needs, but fewer
        assert len(needs) < 5


# ── DecisionBias ─────────────────────────────────────────────────

class TestDecisionBias:
    def test_bias_adds_verification(self):
        bias = DecisionBias()
        state = CognitiveState(caution=0.9, confidence=0.2)
        steps = [{"id": 1, "skill": "code", "risk": "high", "description": "test"}]
        biased = bias.bias_plan(state, steps)
        assert len(biased) > len(steps)

    def test_bias_adds_exploration(self):
        bias = DecisionBias()
        state = CognitiveState(curiosity=0.9, novelty=0.9, frustration=0.1)
        steps = [{"id": 1, "skill": "code"}]
        biased = bias.bias_plan(state, steps)
        assert biased[0]["skill"] == "code"
        assert "explore" in biased[0]["id"]

    def test_should_ask_clarification(self):
        bias = DecisionBias()
        assert bias.should_ask_clarification(CognitiveState(confidence=0.1)) is True
        assert bias.should_ask_clarification(CognitiveState(confidence=0.9)) is False

    def test_confidence_threshold(self):
        bias = DecisionBias()
        high_caution = bias.get_confidence_threshold(CognitiveState(caution=0.9))
        low_caution = bias.get_confidence_threshold(CognitiveState(caution=0.1))
        assert high_caution > low_caution

    def test_retry_limit(self):
        bias = DecisionBias()
        assert bias.get_retry_limit(CognitiveState(persistence=0.9)) == 5
        assert bias.get_retry_limit(CognitiveState(persistence=0.1)) == 1


# ── CognitiveMetrics ─────────────────────────────────────────────

class TestCognitiveMetrics:
    def test_compute_overall(self):
        m = CognitiveMetrics(
            decision_accuracy=0.8, planning_accuracy=0.7,
            execution_success=0.9, recovery_success=0.6,
        )
        overall = m.compute_overall()
        assert 0 < overall < 1

    def test_summary(self):
        m = CognitiveMetrics(decision_accuracy=0.8, execution_success=0.9)
        text = m.summary()
        assert "Decision: 80%" in text


class TestMetricsTracker:
    def test_record_and_compare(self, tmp_path):
        tracker = MetricsTracker(str(tmp_path / "test.db"))
        m1 = CognitiveMetrics(decision_accuracy=0.7, execution_success=0.8)
        m1.compute_overall()
        tracker.record_run("bench1", m1, state_enabled=False)

        m2 = CognitiveMetrics(decision_accuracy=0.9, execution_success=0.95)
        m2.compute_overall()
        tracker.record_run("bench1", m2, state_enabled=True)

        comp = tracker.get_comparison("bench1")
        assert comp["runs_without_state"] == 1
        assert comp["runs_with_state"] == 1
        assert comp["with_state"]["decision_accuracy"] > comp["without_state"]["decision_accuracy"]
        tracker.close()


# ── CognitiveEngine ──────────────────────────────────────────────

class TestCognitiveEngine:
    def test_reason(self, tmp_path):
        engine = CognitiveEngine(
            reasoning=ReasoningEngine(),
            db_path=str(tmp_path / "test.db"),
        )
        plan = engine.reason("analyze code")
        assert len(plan.steps) >= 1
        engine.shutdown()

    def test_update_from_outcome(self, tmp_path):
        engine = CognitiveEngine(
            reasoning=ReasoningEngine(),
            db_path=str(tmp_path / "test.db"),
        )
        engine.update_from_outcome(True)
        assert engine.state.total_successes == 1
        engine.update_from_outcome(False)
        assert engine.state.total_failures == 1
        engine.shutdown()

    def test_should_retry(self, tmp_path):
        engine = CognitiveEngine(
            reasoning=ReasoningEngine(),
            db_path=str(tmp_path / "test.db"),
        )
        for _ in range(3):
            engine.update_from_outcome(False)
        # After 3 failures, persistence is low, retry limit is 2
        assert engine.should_retry() is False
        engine.shutdown()

    def test_get_needs(self, tmp_path):
        engine = CognitiveEngine(
            reasoning=ReasoningEngine(),
            db_path=str(tmp_path / "test.db"),
        )
        engine.update_from_outcome(False)
        engine.update_from_outcome(False)
        needs = engine.get_needs()
        assert len(needs) > 0
        engine.shutdown()

    def test_get_status(self, tmp_path):
        engine = CognitiveEngine(
            reasoning=ReasoningEngine(),
            db_path=str(tmp_path / "test.db"),
        )
        status = engine.get_status()
        assert "state" in status
        assert "needs" in status
        assert "should_ask" in status
        engine.shutdown()

    def test_benchmark(self, tmp_path):
        engine = CognitiveEngine(
            reasoning=ReasoningEngine(),
            db_path=str(tmp_path / "test.db"),
        )
        m = CognitiveMetrics(decision_accuracy=0.8, execution_success=0.9)
        engine.record_benchmark("test_bench", m, state_enabled=True)
        comp = engine.get_benchmark_comparison("test_bench")
        assert comp["runs_with_state"] == 1
        engine.shutdown()

    def test_persistence_across_sessions(self, tmp_path):
        db = str(tmp_path / "test.db")
        e1 = CognitiveEngine(reasoning=ReasoningEngine(), db_path=db)
        e1.update_from_outcome(True)
        e1.shutdown()

        e2 = CognitiveEngine(reasoning=ReasoningEngine(), db_path=db)
        assert e2.state.total_successes == 1
        e2.shutdown()
