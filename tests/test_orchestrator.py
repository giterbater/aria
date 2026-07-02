from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock
from aria_core.orchestrator import CognitiveLoop, LoopState, LoopPhase
from aria_core.cognitive import CognitiveEngine, InternalState
from aria_core.reasoning import ReasoningEngine
from aria_core.skills import SkillManager
from aria_core.skills.builtin import FileSkill, TerminalSkill
from aria_core.skills.builtin.code_skill import CodeSkill
from aria_core.reflection import ReflectionEngine, ReflectionStore
from aria_core.learning import LearningEngine, KnowledgeBase
from aria_core.goals import GoalManager


@pytest.fixture
def loop(tmp_path):
    db = str(tmp_path / "test.db")
    reasoning = ReasoningEngine()
    cognitive = CognitiveEngine(reasoning=reasoning, db_path=db)
    skills = SkillManager()
    skills.register(FileSkill(base_path=str(tmp_path)))
    skills.register(TerminalSkill())
    skills.register(CodeSkill(base_path=str(tmp_path)))
    reflection = ReflectionEngine(store=ReflectionStore(db))
    knowledge = KnowledgeBase(db)
    learning = LearningEngine(knowledge=knowledge, reflection=reflection, db_path=db)
    goals = GoalManager()

    return CognitiveLoop(
        cognitive=cognitive,
        skills=skills,
        reflection=reflection,
        learning=learning,
        goals=goals,
    )


class TestLoopState:
    def test_defaults(self):
        state = LoopState()
        assert state.phase == LoopPhase.IDLE
        assert state.cycle_count == 0

    def test_summary(self):
        state = LoopState()
        text = state.summary()
        assert "idle" in text.lower()
        assert "0" in text


class TestCognitiveLoop:
    def test_run_objective_success(self, loop):
        result = loop.run_objective("scan the codebase")
        assert "success" in result
        assert "phases" in result
        assert "duration_ms" in result
        assert len(result["phases"]) >= 5

    def test_run_objective_records_state(self, loop):
        result = loop.run_objective("analyze code")
        assert loop.state.cycle_count == 1
        assert loop.state.last_cycle_at is not None

    def test_run_objective_reflects(self, loop):
        loop.run_objective("read files")
        reflections = loop._reflection.get_reflections()
        assert len(reflections) >= 1

    def test_run_objective_records_workflow(self, loop):
        loop.run_objective("test something")
        stats = loop._learning.workflow_learner.get_workflow_stats()
        assert stats["total_workflows"] >= 1

    def test_run_objective_updates_cognitive_state(self, loop):
        initial_conf = loop._cognitive.state.confidence
        loop.run_objective("do something")
        assert loop._cognitive.state.cycle_count >= 1

    def test_multiple_objectives(self, loop):
        loop.run_objective("first task")
        loop.run_objective("second task")
        assert loop.state.cycle_count == 2

    def test_stop(self, loop):
        loop.stop()
        assert loop.state.phase == LoopPhase.STOPPED

    def test_get_status(self, loop):
        status = loop.get_status()
        assert "loop" in status
        assert "cognitive" in status
        assert "learning" in status

    def test_callbacks(self, loop):
        phases = []
        results = []
        loop.set_callbacks(
            on_phase=lambda p: phases.append(p),
            on_result=lambda r: results.append(r),
        )
        loop.run_objective("test")
        assert len(phases) > 0
        assert len(results) == 1

    def test_cognitive_bias_applied(self, loop):
        # Build up frustration
        for _ in range(5):
            loop._cognitive.update_from_outcome(False)

        result = loop.run_objective("analyze code")
        # Should still complete despite low confidence
        assert "phases" in result
