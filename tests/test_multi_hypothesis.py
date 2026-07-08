# tests/test_multi_hypothesis.py
"""
Tests for multi-hypothesis reasoning.

Validates that:
1. Multiple hypotheses are generated
2. Plans are scored correctly
3. Best plan is selected
4. Fallback works without LLM
"""

from __future__ import annotations

import pytest
from typing import Any

from aria_core.reasoning.multi_hypothesis import MultiHypothesisReasoner
from aria_core.reasoning.interfaces import ReasoningContext, ReasonedPlan, ConfidenceScore
from aria_core.memory.simple_memory_system import SimpleMemorySystem


class TestMultiHypothesisReasoner:
    """Test multi-hypothesis reasoning engine."""

    def test_initialization(self):
        """Test that reasoner initializes correctly."""
        reasoner = MultiHypothesisReasoner(llm=None, memory=None)
        assert reasoner._llm is None
        assert reasoner._memory is None
        assert reasoner._num_hypotheses == 3

    def test_fallback_hypotheses(self):
        """Test that fallback generates multiple hypotheses without LLM."""
        reasoner = MultiHypothesisReasoner(llm=None, memory=None)
        context = ReasoningContext(objective="test objective")
        
        hypotheses = reasoner.generate_hypotheses("test objective", context)
        
        assert len(hypotheses) >= 2
        assert all(isinstance(h, ReasonedPlan) for h in hypotheses)

    def test_plan_scoring(self):
        """Test that plans are scored correctly."""
        memory = SimpleMemorySystem()
        reasoner = MultiHypothesisReasoner(llm=None, memory=memory)
        context = ReasoningContext(objective="test", available_skills=["code", "terminal"])
        
        # Create a simple plan
        plan = ReasonedPlan(
            objective="test",
            steps=[
                {"id": 1, "skill": "code", "action": "scan", "args": {},
                 "description": "Scan", "dependencies": [], "confidence": 0.8, "risk": "low"},
            ],
            confidence=ConfidenceScore(goal=0.7, plan=0.7, skill_selection=0.8, memory_match=0.5),
        )
        
        score = reasoner.score_plan(plan, context)
        
        assert isinstance(score, float)
        assert score > 0

    def test_select_best(self):
        """Test that best plan is selected from hypotheses."""
        reasoner = MultiHypothesisReasoner(llm=None, memory=None)
        context = ReasoningContext(objective="test", available_skills=["code"])
        
        # Create hypotheses with different quality
        h1 = ReasonedPlan(
            objective="test",
            steps=[
                {"id": 1, "skill": "code", "action": "scan", "args": {},
                 "description": "Scan", "dependencies": [], "confidence": 0.5, "risk": "low"},
                {"id": 2, "skill": "code", "action": "complexity", "args": {},
                 "description": "Analyze", "dependencies": [1], "confidence": 0.5, "risk": "low"},
                {"id": 3, "skill": "terminal", "action": "run", "args": {},
                 "description": "Test", "dependencies": [2], "confidence": 0.5, "risk": "medium"},
            ],
            confidence=ConfidenceScore(goal=0.5, plan=0.5, skill_selection=0.7, memory_match=0.3),
        )
        
        h2 = ReasonedPlan(
            objective="test",
            steps=[
                {"id": 1, "skill": "code", "action": "scan", "args": {},
                 "description": "Scan", "dependencies": [], "confidence": 0.9, "risk": "low"},
            ],
            confidence=ConfidenceScore(goal=0.9, plan=0.9, skill_selection=1.0, memory_match=0.5),
        )
        
        best = reasoner.select_best([h1, h2], context)
        
        # h2 should be selected (fewer steps, higher confidence)
        assert best.confidence.overall > h1.confidence.overall

    def test_adaptive_risk_penalty(self):
        """Test that risk penalty is adaptive, not fixed.
        
        With no memory, there's a small default penalty.
        With memory showing risk succeeds, penalty decreases.
        With memory showing risk fails, penalty increases.
        """
        reasoner = MultiHypothesisReasoner(llm=None, memory=None)
        context = ReasoningContext(objective="test")
        
        low_risk = ReasonedPlan(
            objective="test",
            steps=[
                {"id": 1, "skill": "code", "action": "scan", "args": {},
                 "description": "Scan", "dependencies": [], "confidence": 0.8, "risk": "low"},
            ],
            confidence=ConfidenceScore(goal=0.8, plan=0.8, skill_selection=0.9, memory_match=0.5),
        )
        
        high_risk = ReasonedPlan(
            objective="test",
            steps=[
                {"id": 1, "skill": "code", "action": "scan", "args": {},
                 "description": "Scan", "dependencies": [], "confidence": 0.8, "risk": "high"},
            ],
            confidence=ConfidenceScore(goal=0.8, plan=0.8, skill_selection=0.9, memory_match=0.5),
        )
        
        score_low = reasoner.score_plan(low_risk, context)
        score_high = reasoner.score_plan(high_risk, context)
        
        # With no memory, there's a small default penalty for high risk
        # The difference should be small but present
        assert score_low > score_high
        assert score_low - score_high < 0.1  # Small penalty, not large

    def test_scoring_rewards_skill_availability(self):
        """Test that available skills are rewarded."""
        reasoner = MultiHypothesisReasoner(llm=None, memory=None)
        context = ReasoningContext(objective="test", available_skills=["code", "terminal"])
        
        with_available = ReasonedPlan(
            objective="test",
            steps=[
                {"id": 1, "skill": "code", "action": "scan", "args": {},
                 "description": "Scan", "dependencies": [], "confidence": 0.8, "risk": "low"},
            ],
            confidence=ConfidenceScore(goal=0.8, plan=0.8, skill_selection=0.9, memory_match=0.5),
        )
        
        without_available = ReasonedPlan(
            objective="test",
            steps=[
                {"id": 1, "skill": "unknown_skill", "action": "scan", "args": {},
                 "description": "Scan", "dependencies": [], "confidence": 0.8, "risk": "low"},
            ],
            confidence=ConfidenceScore(goal=0.8, plan=0.8, skill_selection=0.9, memory_match=0.5),
        )
        
        score_with = reasoner.score_plan(with_available, context)
        score_without = reasoner.score_plan(without_available, context)
        
        assert score_with > score_without

    def test_adaptive_complexity_penalty(self):
        """Test that complexity penalty is adaptive, not fixed.
        
        With no memory, there's a small default penalty for >3 steps.
        With memory showing complex plans succeed, penalty decreases.
        """
        reasoner = MultiHypothesisReasoner(llm=None, memory=None)
        context = ReasoningContext(objective="test")
        
        short_plan = ReasonedPlan(
            objective="test",
            steps=[
                {"id": 1, "skill": "code", "action": "scan", "args": {},
                 "description": "Scan", "dependencies": [], "confidence": 0.8, "risk": "low"},
            ],
            confidence=ConfidenceScore(goal=0.8, plan=0.8, skill_selection=0.9, memory_match=0.5),
        )
        
        long_plan = ReasonedPlan(
            objective="test",
            steps=[
                {"id": 1, "skill": "code", "action": "scan", "args": {},
                 "description": "Scan", "dependencies": [], "confidence": 0.8, "risk": "low"},
                {"id": 2, "skill": "code", "action": "complexity", "args": {},
                 "description": "Analyze", "dependencies": [1], "confidence": 0.8, "risk": "low"},
                {"id": 3, "skill": "terminal", "action": "run", "args": {},
                 "description": "Test", "dependencies": [2], "confidence": 0.8, "risk": "low"},
                {"id": 4, "skill": "code", "action": "scan", "args": {},
                 "description": "Re-scan", "dependencies": [3], "confidence": 0.8, "risk": "low"},
                {"id": 5, "skill": "terminal", "action": "run", "args": {},
                 "description": "Re-test", "dependencies": [4], "confidence": 0.8, "risk": "low"},
            ],
            confidence=ConfidenceScore(goal=0.8, plan=0.8, skill_selection=0.9, memory_match=0.5),
        )
        
        score_short = reasoner.score_plan(short_plan, context)
        score_long = reasoner.score_plan(long_plan, context)
        
        # With no memory, there's a small default penalty for >3 steps
        # Short plan should score slightly higher
        assert score_short > score_long
        assert score_short - score_long < 0.1  # Small penalty, not large


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
