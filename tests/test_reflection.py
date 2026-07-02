from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock
from aria_core.reflection import ReflectionEngine, Reflection, Lesson, ReflectionType


class TestReflection:
    def test_creation(self):
        r = Reflection(summary="test reflection")
        assert r.summary == "test reflection"
        assert r.reflection_type == ReflectionType.OBSERVATION
        assert r.lessons == []


class TestLesson:
    def test_creation(self):
        l = Lesson(text="learned something", tags=["test"])
        assert l.text == "learned something"
        assert "test" in l.tags


class TestReflectionEngineStub:
    def test_reflect_success(self):
        engine = ReflectionEngine()
        r = engine.reflect("run_tests", "All 10 tests passed")
        assert r.reflection_type == ReflectionType.SUCCESS
        assert len(r.lessons) == 1
        assert "repeat" in r.lessons[0].tags

    def test_reflect_failure(self):
        engine = ReflectionEngine()
        r = engine.reflect("run_tests", "Error: test_memory.py FAILED")
        assert r.reflection_type == ReflectionType.FAILURE
        assert len(r.what_failed) == 1
        assert "avoid" in r.lessons[0].tags

    def test_reflect_unknown(self):
        engine = ReflectionEngine()
        r = engine.reflect("read_file", "File contents shown above")
        assert r.reflection_type == ReflectionType.OBSERVATION

    def test_reflections_accumulate(self):
        engine = ReflectionEngine()
        engine.reflect("a", "success")
        engine.reflect("b", "error occurred")
        assert len(engine.get_reflections()) == 2

    def test_get_reflections_limit(self):
        engine = ReflectionEngine()
        for i in range(10):
            engine.reflect(f"action_{i}", "result")
        assert len(engine.get_reflections(limit=3)) == 3

    def test_lessons_accumulate(self):
        engine = ReflectionEngine()
        engine.reflect("a", "success")
        engine.reflect("b", "error failed")
        assert len(engine.get_lessons()) == 2

    def test_get_lessons_by_tags(self):
        engine = ReflectionEngine()
        engine.reflect("a", "success passed")
        engine.reflect("b", "error failed")
        success_lessons = engine.get_lessons(tags=["success"])
        assert len(success_lessons) == 1
        failure_lessons = engine.get_lessons(tags=["failure"])
        assert len(failure_lessons) == 1

    def test_learned_patterns(self):
        engine = ReflectionEngine()
        engine.reflect("a", "success passed")
        engine.reflect("b", "success ok")
        engine.reflect("c", "error failed")
        patterns = engine.get_learned_patterns()
        assert patterns["success"] == 2
        assert patterns["failure"] == 1

    def test_summarize_empty(self):
        engine = ReflectionEngine()
        text = engine.summarize()
        assert "0 total" in text or "No reflections" in text

    def test_summarize_with_data(self):
        engine = ReflectionEngine()
        engine.reflect("a", "success passed")
        engine.reflect("b", "error failed")
        summary = engine.summarize()
        assert "2 total" in summary
        assert "1 success" in summary
        assert "1 failure" in summary


class TestReflectionEngineLLM:
    def test_reflect_with_llm(self):
        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = json.dumps({
            "reflection_type": "success",
            "summary": "tests passed",
            "what_worked": ["test suite is solid"],
            "what_failed": [],
            "what_to_improve": [],
            "lessons": [{"text": "keep test coverage high", "tags": ["testing", "quality"]}],
        })
        mock_llm.generate.return_value = mock_resp

        engine = ReflectionEngine(llm=mock_llm)
        r = engine.reflect("run_tests", "All tests passed")
        assert r.reflection_type == ReflectionType.SUCCESS
        assert r.summary == "tests passed"
        assert len(r.lessons) == 1
        assert "testing" in r.lessons[0].tags

    def test_llm_failure_falls_back(self):
        mock_llm = MagicMock()
        mock_llm.generate.side_effect = Exception("LLM down")

        engine = ReflectionEngine(llm=mock_llm)
        r = engine.reflect("run_tests", "error failed")
        assert r.reflection_type == ReflectionType.FAILURE

    def test_invalid_json_falls_back(self):
        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "not json"
        mock_llm.generate.return_value = mock_resp

        engine = ReflectionEngine(llm=mock_llm)
        r = engine.reflect("action", "success ok")
        assert r.reflection_type == ReflectionType.SUCCESS
