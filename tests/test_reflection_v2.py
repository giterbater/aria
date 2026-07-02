from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock
from aria_core.reflection import (
    ReflectionEngine, ReflectionStore, Reflection, Lesson,
    ReflectionType, SkillOutcome, ReflectionSummary,
)


class TestReflectionStore:
    def test_save_and_load_reflection(self, tmp_path):
        store = ReflectionStore(str(tmp_path / "test.db"))
        r = Reflection(
            summary="test reflection",
            reflection_type=ReflectionType.SUCCESS,
            what_worked=["it worked"],
            lessons=[Lesson(text="lesson 1", tags=["tag1"])],
        )
        store.save_reflection(r)
        loaded = store.load_reflections()
        store.close()
        assert len(loaded) == 1
        assert loaded[0].summary == "test reflection"
        assert loaded[0].reflection_type == ReflectionType.SUCCESS
        assert len(loaded[0].lessons) == 1
        assert loaded[0].lessons[0].tags == ["tag1"]

    def test_load_lessons_by_tags(self, tmp_path):
        store = ReflectionStore(str(tmp_path / "test.db"))
        r = Reflection(
            summary="test",
            lessons=[
                Lesson(text="l1", tags=["a", "b"]),
                Lesson(text="l2", tags=["c"]),
            ],
        )
        store.save_reflection(r)
        lessons = store.load_lessons(tags=["a"])
        store.close()
        assert len(lessons) == 1
        assert lessons[0].text == "l1"

    def test_skill_outcomes(self, tmp_path):
        store = ReflectionStore(str(tmp_path / "test.db"))
        store.save_skill_outcome("file", "read", True, 10.0)
        store.save_skill_outcome("file", "write", False, 5.0, errors=["fail"])
        store.save_skill_outcome("terminal", "run", True, 20.0)

        stats = store.get_skill_stats()
        assert stats["file"]["success"] == 1
        assert stats["file"]["failure"] == 1

        rate = store.get_success_rate("file")
        assert rate == 0.5

        rate2 = store.get_success_rate("terminal")
        assert rate2 == 1.0
        store.close()

    def test_persistence_survives_restart(self, tmp_path):
        db = tmp_path / "test.db"
        store1 = ReflectionStore(str(db))
        r = Reflection(summary="persistent", reflection_type=ReflectionType.SUCCESS)
        store1.save_reflection(r)
        store1.close()

        store2 = ReflectionStore(str(db))
        loaded = store2.load_reflections()
        store2.close()
        assert len(loaded) == 1
        assert loaded[0].summary == "persistent"


class TestSkillOutcome:
    def test_creation(self):
        so = SkillOutcome(skill_name="file", action="read", success=True, duration_ms=5.0)
        assert so.skill_name == "file"
        assert so.success is True


class TestReflectionSummary:
    def test_defaults(self):
        rs = ReflectionSummary()
        assert rs.total_reflections == 0
        assert rs.skill_success_rates == {}
        assert rs.recommendations == []


class TestEngineV2:
    def test_reflect_persists(self, tmp_path):
        engine = ReflectionEngine(store=ReflectionStore(str(tmp_path / "test.db")))
        engine.reflect("run_tests", "All tests passed")
        assert len(engine.get_reflections()) == 1
        # Verify persistence
        engine2 = ReflectionEngine(store=ReflectionStore(str(tmp_path / "test.db")))
        assert len(engine2.get_reflections()) == 1

    def test_reflect_skill(self, tmp_path):
        engine = ReflectionEngine(store=ReflectionStore(str(tmp_path / "test.db")))
        outcome = SkillOutcome(
            skill_name="file", action="read", success=True,
            duration_ms=5.0, output="file contents",
        )
        r = engine.reflect_skill(outcome)
        assert r.reflection_type == ReflectionType.SUCCESS
        assert engine.get_success_rate("file") == 1.0

    def test_reflect_skill_failure(self, tmp_path):
        engine = ReflectionEngine(store=ReflectionStore(str(tmp_path / "test.db")))
        outcome = SkillOutcome(
            skill_name="terminal", action="run", success=False,
            errors=["command failed"],
        )
        r = engine.reflect_skill(outcome)
        assert r.reflection_type == ReflectionType.FAILURE

    def test_get_summary(self, tmp_path):
        engine = ReflectionEngine(store=ReflectionStore(str(tmp_path / "test.db")))
        engine.reflect("a", "success passed")
        engine.reflect("b", "error failed")
        engine.reflect_skill(SkillOutcome("file", "read", True, 5.0))
        engine.reflect_skill(SkillOutcome("file", "write", False, 10.0, errors=["fail"]))

        summary = engine.get_summary()
        assert summary.total_reflections == 4
        assert summary.successes == 2
        assert summary.failures == 2
        assert "file" in summary.skill_success_rates
        assert summary.skill_success_rates["file"] == 0.5

    def test_recommendations_low_success(self, tmp_path):
        engine = ReflectionEngine(store=ReflectionStore(str(tmp_path / "test.db")))
        for _ in range(5):
            engine.reflect_skill(SkillOutcome("bad_skill", "run", False, errors=["fail"]))
        summary = engine.get_summary()
        assert any("investigate" in r for r in summary.recommendations)

    def test_recommendations_high_failure_rate(self, tmp_path):
        engine = ReflectionEngine(store=ReflectionStore(str(tmp_path / "test.db")))
        for _ in range(3):
            engine.reflect("action", "error failed")
        for _ in range(2):
            engine.reflect("action", "success ok")
        summary = engine.get_summary()
        assert any("failure rate" in r for r in summary.recommendations)

    def test_summarize(self, tmp_path):
        engine = ReflectionEngine(store=ReflectionStore(str(tmp_path / "test.db")))
        engine.reflect("a", "success passed")
        engine.reflect_skill(SkillOutcome("file", "read", True, 5.0))
        text = engine.summarize()
        assert "success" in text
        assert "file" in text

    def test_hydration_from_store(self, tmp_path):
        db = tmp_path / "test.db"
        engine1 = ReflectionEngine(store=ReflectionStore(str(db)))
        engine1.reflect("a", "success ok")
        engine1.reflect("b", "error failed")

        engine2 = ReflectionEngine(store=ReflectionStore(str(db)))
        assert len(engine2.get_reflections()) == 2
        assert len(engine2.get_lessons()) == 2
