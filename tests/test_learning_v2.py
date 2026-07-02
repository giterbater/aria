from __future__ import annotations

import json
import pytest
from aria_core.learning import (
    LearningEngine, KnowledgeBase, SkillTracker, SkillProfile,
    WorkflowLearner,
)
from aria_core.reflection import ReflectionEngine, ReflectionStore, SkillOutcome


# ── SkillTracker ─────────────────────────────────────────────────

class TestSkillTracker:
    def test_record_and_get(self, tmp_path):
        tracker = SkillTracker(str(tmp_path / "test.db"))
        tracker.record("file", True, 10.0, "read")
        tracker.record("file", True, 15.0, "write")
        tracker.record("file", False, 20.0, "bad_op")

        profile = tracker.get_profile("file")
        assert profile is not None
        assert profile.total_calls == 3
        assert profile.successes == 2
        assert profile.failures == 1
        assert profile.success_rate == pytest.approx(2 / 3)
        tracker.close()

    def test_get_best_skill(self, tmp_path):
        tracker = SkillTracker(str(tmp_path / "test.db"))
        for _ in range(5):
            tracker.record("file", True, 10.0)
        for _ in range(5):
            tracker.record("terminal", False, 100.0)

        best = tracker.get_best_skill()
        assert best == "file"
        tracker.close()

    def test_get_best_skill_by_keywords(self, tmp_path):
        tracker = SkillTracker(str(tmp_path / "test.db"))
        tracker.record("file", True, 10.0, "read file")
        tracker.record("terminal", True, 10.0, "run command")

        best = tracker.get_best_skill(["file", "read"])
        assert best == "file"
        tracker.close()

    def test_unreliable_skills(self, tmp_path):
        tracker = SkillTracker(str(tmp_path / "test.db"))
        for _ in range(5):
            tracker.record("bad_skill", False, 100.0)

        unreliable = tracker.get_unreliable_skills()
        assert len(unreliable) == 1
        assert unreliable[0].name == "bad_skill"
        tracker.close()

    def test_slow_skills(self, tmp_path):
        tracker = SkillTracker(str(tmp_path / "test.db"))
        tracker.record("slow", True, 10000.0)
        tracker.record("fast", True, 5.0)

        slow = tracker.get_slow_skills()
        assert len(slow) == 1
        assert slow[0].name == "slow"
        tracker.close()

    def test_persistence(self, tmp_path):
        db = str(tmp_path / "test.db")
        t1 = SkillTracker(db)
        t1.record("file", True, 10.0)
        t1.close()

        t2 = SkillTracker(db)
        profile = t2.get_profile("file")
        assert profile is not None
        assert profile.total_calls == 1
        t2.close()


class TestSkillProfile:
    def test_reliability(self):
        p = SkillProfile(name="test", total_calls=10, successes=9, failures=1)
        assert p.reliability == pytest.approx(0.9)

    def test_reliability_low_volume(self):
        p = SkillProfile(name="test", total_calls=2, successes=2, failures=0)
        assert p.reliability == 0.5

    def test_success_rate(self):
        p = SkillProfile(name="test", total_calls=0)
        assert p.success_rate == 0.0


# ── WorkflowLearner ──────────────────────────────────────────────

class TestWorkflowLearner:
    def test_record_and_suggest(self, tmp_path):
        kb = KnowledgeBase(str(tmp_path / "kb.db"))
        learner = WorkflowLearner(kb)

        learner.record_workflow("test code", ["scan", "run_tests", "commit"], success=True)
        learner.record_workflow("test code", ["scan", "run_tests"], success=False)

        suggested = learner.suggest_workflow("test code")
        assert suggested is not None
        assert "scan" in suggested

    def test_no_suggestion_unknown_task(self, tmp_path):
        kb = KnowledgeBase(str(tmp_path / "kb.db"))
        learner = WorkflowLearner(kb)
        suggested = learner.suggest_workflow("quantum computing")
        assert suggested is None

    def test_get_similar_tasks(self, tmp_path):
        kb = KnowledgeBase(str(tmp_path / "kb.db"))
        learner = WorkflowLearner(kb)
        learner.record_workflow("test code", ["scan"], success=True)
        learner.record_workflow("run tests", ["execute"], success=True)

        similar = learner.get_similar_tasks("test code")
        assert len(similar) > 0

    def test_workflow_stats(self, tmp_path):
        kb = KnowledgeBase(str(tmp_path / "kb.db"))
        learner = WorkflowLearner(kb)
        learner.record_workflow("a", ["x"], success=True)
        learner.record_workflow("b", ["y"], success=False)

        stats = learner.get_workflow_stats()
        assert stats["total_workflows"] == 2
        assert stats["successful"] == 1
        assert stats["success_rate"] == 0.5


# ── LearningEngine v2 ────────────────────────────────────────────

class TestLearningEngineV2:
    def test_record_skill_use(self, tmp_path):
        engine = LearningEngine(db_path=str(tmp_path / "test.db"))
        engine.record_skill_use(SkillOutcome("file", "read", True, 10.0))
        engine.record_skill_use(SkillOutcome("file", "write", False, 20.0, errors=["fail"]))

        profiles = engine.get_skill_profiles()
        assert len(profiles) == 1
        assert profiles[0].total_calls == 2
        engine._knowledge.close()
        engine._skill_tracker.close()

    def test_record_workflow(self, tmp_path):
        engine = LearningEngine(db_path=str(tmp_path / "test.db"))
        engine.record_workflow("test code", ["scan", "run_tests"], True)

        stats = engine.workflow_learner.get_workflow_stats()
        assert stats["total_workflows"] == 1
        engine._knowledge.close()
        engine._skill_tracker.close()

    def test_suggest_workflow(self, tmp_path):
        engine = LearningEngine(db_path=str(tmp_path / "test.db"))
        engine.record_workflow("test code", ["scan", "run_tests"], True)

        suggested = engine.suggest_workflow("test code")
        assert suggested is not None
        engine._knowledge.close()
        engine._skill_tracker.close()

    def test_recommend_skill(self, tmp_path):
        engine = LearningEngine(db_path=str(tmp_path / "test.db"))
        engine.record_skill_use(SkillOutcome("file", "read", True, 10.0))
        engine.record_skill_use(SkillOutcome("file", "read", True, 10.0))

        best = engine.recommend_skill(["file"])
        assert best == "file"
        engine._knowledge.close()
        engine._skill_tracker.close()

    def test_get_knowledge_summary(self, tmp_path):
        engine = LearningEngine(db_path=str(tmp_path / "test.db"))
        engine.record_skill_use(SkillOutcome("file", "read", True, 10.0))
        engine.record_workflow("test", ["x"], True)

        summary = engine.get_knowledge_summary()
        assert "Knowledge:" in summary
        assert "Skills tracked:" in summary
        assert "Workflows:" in summary
        engine._knowledge.close()
        engine._skill_tracker.close()

    def test_learn_from_reflections(self, tmp_path):
        kb = KnowledgeBase(str(tmp_path / "kb.db"))
        store = ReflectionStore(str(tmp_path / "ref.db"))
        ref = ReflectionEngine(store=store)
        engine = LearningEngine(knowledge=kb, reflection=ref, db_path=str(tmp_path / "test.db"))

        ref.reflect("action_a", "success passed")
        ref.reflect("action_b", "error failed")

        new_count = engine.learn_from_reflections()
        assert new_count > 0
        assert kb.count() > 0
        engine._knowledge.close()
        engine._skill_tracker.close()
