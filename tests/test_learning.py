from __future__ import annotations

import json
import pytest
from aria_core.learning import KnowledgeBase, KnowledgeEntry, KnowledgeType, LearningEngine, DecisionInfluencer
from aria_core.reflection import ReflectionEngine, ReflectionStore, SkillOutcome, ReflectionType


# ── KnowledgeBase ────────────────────────────────────────────────

class TestKnowledgeBase:
    def test_store_and_get(self, tmp_path):
        kb = KnowledgeBase(str(tmp_path / "test.db"))
        entry = KnowledgeEntry(
            knowledge_type=KnowledgeType.FACT,
            key="python_version",
            value="Python 3.10",
        )
        kb.store(entry)
        loaded = kb.get("python_version")
        kb.close()
        assert loaded is not None
        assert loaded.value == "Python 3.10"

    def test_search(self, tmp_path):
        kb = KnowledgeBase(str(tmp_path / "test.db"))
        kb.store(KnowledgeEntry(key="file_reader", value="Read files from disk", tags=["file"]))
        kb.store(KnowledgeEntry(key="terminal_exec", value="Execute shell commands", tags=["shell"]))
        results = kb.search("file")
        kb.close()
        assert len(results) == 1
        assert results[0].key == "file_reader"

    def test_get_by_type(self, tmp_path):
        kb = KnowledgeBase(str(tmp_path / "test.db"))
        kb.store(KnowledgeEntry(knowledge_type=KnowledgeType.FACT, key="a", value="1"))
        kb.store(KnowledgeEntry(knowledge_type=KnowledgeType.PATTERN, key="b", value="2"))
        assert len(kb.get_by_type(KnowledgeType.FACT)) == 1
        assert len(kb.get_by_type(KnowledgeType.PATTERN)) == 1
        kb.close()

    def test_get_by_tags(self, tmp_path):
        kb = KnowledgeBase(str(tmp_path / "test.db"))
        kb.store(KnowledgeEntry(key="a", value="1", tags=["file", "read"]))
        kb.store(KnowledgeEntry(key="b", value="2", tags=["shell"]))
        results = kb.get_by_tags(["file"])
        kb.close()
        assert len(results) == 1

    def test_reinforce_and_weaken(self, tmp_path):
        kb = KnowledgeBase(str(tmp_path / "test.db"))
        entry = KnowledgeEntry(key="test", value="v", confidence=0.5)
        kb.store(entry)
        kb.reinforce(entry.id, 0.2)
        loaded = kb.get("test")
        assert loaded.confidence == pytest.approx(0.7)
        kb.weaken(entry.id, 0.3)
        loaded = kb.get("test")
        assert loaded.confidence == pytest.approx(0.4)
        kb.close()

    def test_record_use(self, tmp_path):
        kb = KnowledgeBase(str(tmp_path / "test.db"))
        entry = KnowledgeEntry(key="test", value="v")
        kb.store(entry)
        kb.record_use(entry.id)
        kb.record_use(entry.id)
        loaded = kb.get("test")
        kb.close()
        assert loaded.use_count == 2
        assert loaded.last_used is not None

    def test_count(self, tmp_path):
        kb = KnowledgeBase(str(tmp_path / "test.db"))
        kb.store(KnowledgeEntry(key="a", value="1"))
        kb.store(KnowledgeEntry(key="b", value="2"))
        assert kb.count() == 2
        kb.close()

    def test_count_by_type(self, tmp_path):
        kb = KnowledgeBase(str(tmp_path / "test.db"))
        kb.store(KnowledgeEntry(knowledge_type=KnowledgeType.FACT, key="a", value="1"))
        kb.store(KnowledgeEntry(knowledge_type=KnowledgeType.FACT, key="b", value="2"))
        kb.store(KnowledgeEntry(knowledge_type=KnowledgeType.PATTERN, key="c", value="3"))
        counts = kb.count_by_type()
        kb.close()
        assert counts["fact"] == 2
        assert counts["pattern"] == 1

    def test_delete(self, tmp_path):
        kb = KnowledgeBase(str(tmp_path / "test.db"))
        entry = KnowledgeEntry(key="test", value="v")
        kb.store(entry)
        kb.delete(entry.id)
        assert kb.get("test") is None
        kb.close()

    def test_persistence(self, tmp_path):
        db = tmp_path / "test.db"
        kb1 = KnowledgeBase(str(db))
        kb1.store(KnowledgeEntry(key="persistent", value="data"))
        kb1.close()
        kb2 = KnowledgeBase(str(db))
        assert kb2.get("persistent") is not None
        kb2.close()


# ── LearningEngine ───────────────────────────────────────────────

class TestLearningEngine:
    def test_learn_from_reflections(self, tmp_path):
        kb = KnowledgeBase(str(tmp_path / "kb.db"))
        store = ReflectionStore(str(tmp_path / "ref.db"))
        ref = ReflectionEngine(store=store)
        engine = LearningEngine(knowledge=kb, reflection=ref)

        ref.reflect("run_tests", "All tests passed")
        ref.reflect("run_tests", "Error: test failed")

        new_count = engine.learn_from_reflections()
        assert new_count > 0
        assert kb.count() > 0

    def test_learn_from_skill_stats(self, tmp_path):
        kb = KnowledgeBase(str(tmp_path / "kb.db"))
        store = ReflectionStore(str(tmp_path / "ref.db"))
        ref = ReflectionEngine(store=store)
        engine = LearningEngine(knowledge=kb, reflection=ref)

        for _ in range(5):
            ref.reflect_skill(SkillOutcome("file", "read", True, 5.0))
        for _ in range(5):
            ref.reflect_skill(SkillOutcome("bad_skill", "run", False, 100.0, errors=["fail"]))

        new_count = engine.learn_from_skill_stats()
        assert new_count > 0
        assert kb.count() > 0

    def test_learn_workflow(self, tmp_path):
        kb = KnowledgeBase(str(tmp_path / "kb.db"))
        engine = LearningEngine(knowledge=kb)
        engine.learn_workflow("test code", ["scan", "run_tests", "commit"], success=True)
        assert kb.count() > 0

    def test_get_relevant_knowledge(self, tmp_path):
        kb = KnowledgeBase(str(tmp_path / "kb.db"))
        engine = LearningEngine(knowledge=kb)
        kb.store(KnowledgeEntry(key="file_reader", value="Read files", tags=["file"]))
        results = engine.get_relevant_knowledge("file reader")
        assert len(results) > 0

    def test_get_knowledge_summary(self, tmp_path):
        kb = KnowledgeBase(str(tmp_path / "kb.db"))
        engine = LearningEngine(knowledge=kb)
        kb.store(KnowledgeEntry(key="a", value="1"))
        summary = engine.get_knowledge_summary()
        assert "1 entries" in summary

    def test_learn_from_no_reflections(self):
        engine = LearningEngine()
        assert engine.learn_from_reflections() == 0
        assert engine.learn_from_skill_stats() == 0


# ── DecisionInfluencer ───────────────────────────────────────────

class TestDecisionInfluencer:
    def test_get_context_for_task(self, tmp_path):
        kb = KnowledgeBase(str(tmp_path / "kb.db"))
        engine = LearningEngine(knowledge=kb)
        kb.store(KnowledgeEntry(
            knowledge_type=KnowledgeType.SUCCESS_STRATEGY,
            key="test strategy", value="Always run tests first",
            tags=["success", "strategy"],
        ))
        kb.store(KnowledgeEntry(
            knowledge_type=KnowledgeType.FAILURE_MODE,
            key="skip tests", value="Never skip tests",
            tags=["failure", "mode"],
        ))

        influencer = DecisionInfluencer(engine)
        context = influencer.get_context_for_task("test something")
        assert len(context["strategies"]) > 0
        assert len(context["warnings"]) > 0

    def test_should_use_skill(self, tmp_path):
        kb = KnowledgeBase(str(tmp_path / "kb.db"))
        engine = LearningEngine(knowledge=kb)
        kb.store(KnowledgeEntry(
            key="skill:file:reliable", value="File skill works well",
            tags=["skill", "file", "reliable"],
        ))

        influencer = DecisionInfluencer(engine)
        should, reason = influencer.should_use_skill("file")
        assert should is True
        assert "reliable" in reason

    def test_should_not_use_skill(self, tmp_path):
        kb = KnowledgeBase(str(tmp_path / "kb.db"))
        engine = LearningEngine(knowledge=kb)
        kb.store(KnowledgeEntry(
            key="skill:broken:unreliable", value="Broken skill fails often",
            tags=["skill", "broken", "unreliable"],
        ))

        influencer = DecisionInfluencer(engine)
        should, reason = influencer.should_use_skill("broken")
        assert should is False

    def test_build_recommendation_prompt(self, tmp_path):
        kb = KnowledgeBase(str(tmp_path / "kb.db"))
        engine = LearningEngine(knowledge=kb)
        kb.store(KnowledgeEntry(
            knowledge_type=KnowledgeType.SUCCESS_STRATEGY,
            key="strategy", value="Use file skill for reading",
            tags=["success"],
        ))

        influencer = DecisionInfluencer(engine)
        prompt = influencer.build_recommendation_prompt("read files")
        assert "Past strategies" in prompt

    def test_workflow_suggestion(self, tmp_path):
        kb = KnowledgeBase(str(tmp_path / "kb.db"))
        engine = LearningEngine(knowledge=kb)
        engine.learn_workflow("test code", ["scan", "run_tests", "commit"], success=True)

        influencer = DecisionInfluencer(engine)
        steps = influencer.get_workflow_suggestion("test code")
        assert steps is not None
        assert "scan" in steps
