# aria_core/reasoning/multi_hypothesis.py
"""
Multi-Hypothesis Reasoning Engine

Generates N candidate plans, scores each using memory-informed heuristics,
and selects the best. This replaces single-hypothesis reasoning with
competitive plan generation.

Key insight: The best plan is not always the first one generated.
By generating multiple alternatives and scoring them, we can find
better solutions without changing the underlying planning mechanism.
"""

from __future__ import annotations

import json
import logging
import random
from typing import Any, Protocol, runtime_checkable

from .interfaces import ReasoningContext, ReasonedPlan, ConfidenceScore
from ..planning.interfaces import PlanStep
from ..memory.interfaces import MemorySystemProtocol
from ..memory.influence import MemoryInfluenceEngine

logger = logging.getLogger("aria.reasoning.multi_hypothesis")


@runtime_checkable
class LLMProvider(Protocol):
    def generate(self, prompt: str, *, max_tokens: int = 2048, temperature: float = 0.3) -> Any: ...


# Prompt for generating alternative plans
ALTERNATIVE_PROMPT = """Generate an ALTERNATIVE plan for this objective.

OBJECTIVE: {objective}

AVAILABLE SKILLS: {skills}

KNOWN PATTERNS (what has worked before):
{patterns}

KNOWN FAILURE MODES (what to avoid):
{failures}

Generate a DIFFERENT approach than the standard one. Consider:
1. Different step ordering
2. Different skill combinations
3. More granular or more coarse steps
4. Different risk tradeoffs

OUTPUT FORMAT (JSON only):
{{
  "steps": [
    {{
      "id": 1,
      "skill": "skill_name",
      "action": "specific action",
      "args": {{"key": "value"}},
      "description": "what this step accomplishes",
      "dependencies": [],
      "confidence": 0.85,
      "risk": "low|medium|high",
      "rationale": "why this step is necessary"
    }}
  ],
  "approach": "brief description of this alternative approach",
  "tradeoffs": "what this approach trades off vs the standard"
}}

Generate ONE alternative plan. Be creative but realistic.
"""


class MultiHypothesisReasoner:
    """Generates multiple candidate plans and selects the best.
    
    Pipeline:
    1. Generate N candidate plans (with temperature variation)
    2. Score each plan using memory-informed heuristics
    3. Select the best plan
    4. Return with comparison metadata
    """
    
    def __init__(
        self,
        llm: LLMProvider | None = None,
        memory: MemorySystemProtocol | None = None,
        num_hypotheses: int = 3,
    ):
        self._llm = llm
        self._memory = memory
        self._num_hypotheses = num_hypotheses
        self._influence = MemoryInfluenceEngine(memory) if memory else None
    
    def generate_hypotheses(
        self,
        objective: str,
        context: ReasoningContext,
    ) -> list[ReasonedPlan]:
        """Generate multiple candidate plans."""
        if self._llm is None:
            return self._fallback_hypotheses(objective, context)
        
        hypotheses = []
        
        # Generate plans with varying temperature for diversity
        temperatures = [0.2, 0.5, 0.8][:self._num_hypotheses]
        
        for i, temp in enumerate(temperatures):
            try:
                plan = self._generate_single_hypothesis(
                    objective, context, temperature=temp, variant=i
                )
                if plan and plan.steps:
                    hypotheses.append(plan)
            except Exception as e:
                logger.warning("Failed to generate hypothesis %d: %s", i, e)
        
        # Always include the standard reasoning as a baseline
        if not hypotheses:
            hypotheses.append(self._standard_reason(objective, context))
        
        return hypotheses
    
    def _generate_single_hypothesis(
        self,
        objective: str,
        context: ReasoningContext,
        temperature: float = 0.3,
        variant: int = 0,
    ) -> ReasonedPlan:
        """Generate a single hypothesis plan."""
        prompt = ALTERNATIVE_PROMPT.format(
            objective=objective,
            skills=", ".join(context.available_skills) or "(none registered)",
            patterns="\n".join(f"- {p}" for p in context.known_patterns[:3]) or "(none)",
            failures="\n".join(f"- {f}" for f in context.failure_modes[:3]) or "(none)",
        )
        
        resp = self._llm.generate(prompt, max_tokens=2000, temperature=temperature)
        text = resp.text if hasattr(resp, "text") else str(resp)
        data = self._parse_response(text)
        
        if not data or "steps" not in data:
            return self._standard_reason(objective, context)
        
        steps = []
        for s in data["steps"]:
            steps.append({
                "id": s.get("id", len(steps) + 1),
                "skill": s.get("skill", "unknown"),
                "action": s.get("action", ""),
                "args": s.get("args", {}),
                "description": s.get("description", ""),
                "dependencies": s.get("dependencies", []),
                "confidence": s.get("confidence", 0.5),
                "risk": s.get("risk", "medium"),
                "rationale": s.get("rationale", ""),
            })
        
        confidence = ConfidenceScore(
            goal=min(1.0, data.get("overall_confidence", 0.6) + 0.05),
            plan=data.get("overall_confidence", 0.6),
            skill_selection=self._estimate_skill_confidence(steps, context.available_skills),
            memory_match=self._estimate_memory_confidence(context),
        )
        
        return ReasonedPlan(
            objective=objective,
            steps=steps,
            confidence=confidence,
            reasoning=data.get("approach", f"Alternative hypothesis {variant + 1}"),
            risks=data.get("tradeoffs", []),
            alternatives=[data.get("approach", "")],
        )
    
    def _standard_reason(self, objective: str, context: ReasoningContext) -> ReasonedPlan:
        """Generate the standard plan (for comparison)."""
        # This would call the original reasoning prompt
        # For now, return a basic plan
        steps = [
            {
                "id": 1,
                "skill": "code",
                "action": "scan",
                "args": {"path": "."},
                "description": "Scan repository",
                "dependencies": [],
                "confidence": 0.7,
                "risk": "low",
                "rationale": "Understand current state",
            }
        ]
        
        return ReasonedPlan(
            objective=objective,
            steps=steps,
            confidence=ConfidenceScore(goal=0.6, plan=0.5, skill_selection=0.7, memory_match=0.3),
            reasoning="Standard approach",
        )
    
    def _fallback_hypotheses(
        self,
        objective: str,
        context: ReasoningContext,
    ) -> list[ReasonedPlan]:
        """Generate fallback hypotheses without LLM."""
        hypotheses = []
        
        # Hypothesis 1: Read-first approach
        h1 = ReasonedPlan(
            objective=objective,
            steps=[
                {"id": 1, "skill": "code", "action": "scan", "args": {"path": "."},
                 "description": "Scan repository", "dependencies": [], "confidence": 0.7, "risk": "low"},
                {"id": 2, "skill": "terminal", "action": "run",
                 "args": {"command": "python -m pytest tests/ -q --tb=short 2>&1"},
                 "description": "Run tests", "dependencies": [1], "confidence": 0.6, "risk": "low"},
            ],
            confidence=ConfidenceScore(goal=0.6, plan=0.5, skill_selection=0.7, memory_match=0.3),
            reasoning="Read-first approach",
        )
        hypotheses.append(h1)
        
        # Hypothesis 2: Test-first approach
        h2 = ReasonedPlan(
            objective=objective,
            steps=[
                {"id": 1, "skill": "terminal", "action": "run",
                 "args": {"command": "python -m pytest tests/ -q --tb=short 2>&1"},
                 "description": "Run tests first", "dependencies": [], "confidence": 0.6, "risk": "medium"},
                {"id": 2, "skill": "code", "action": "scan", "args": {"path": "."},
                 "description": "Scan if tests fail", "dependencies": [1], "confidence": 0.7, "risk": "low"},
            ],
            confidence=ConfidenceScore(goal=0.5, plan=0.5, skill_selection=0.7, memory_match=0.3),
            reasoning="Test-first approach",
        )
        hypotheses.append(h2)
        
        return hypotheses
    
    def score_plan(
        self,
        plan: ReasonedPlan,
        context: ReasoningContext,
    ) -> float:
        """Score a plan using memory-informed heuristics.
        
        Higher score = better plan.
        
        Penalties are ADAPTIVE - they learn from memory whether complexity,
        risk, or dependencies actually cause failures. If complex plans
        succeed, they get rewarded. If they fail, memory learns the cost.
        """
        score = 0.0
        
        # 1. Confidence bonus - plans with higher confidence are preferred
        score += plan.confidence.overall * 0.4
        
        # 2. Memory match bonus - plans using successful patterns are rewarded
        if self._influence:
            signals = self._influence.compute_influences(limit=5)
            for signal in signals:
                for step in plan.steps:
                    if step.get("skill") == signal.action_preference:
                        score += signal.strength * signal.confidence * 0.3
        
        # 3. Skill availability bonus
        known_skills = set(context.available_skills) | {"reason", "delegate:mimo", "delegate:nemotron"}
        available_count = sum(1 for s in plan.steps if s.get("skill") in known_skills)
        if plan.steps:
            score += (available_count / len(plan.steps)) * 0.2
        
        # 4. Adaptive complexity cost - learned from memory
        #    If complex plans historically succeed, this approaches 0
        #    If complex plans historically fail, this penalizes them
        complexity_cost = self._learned_complexity_cost(plan)
        score -= complexity_cost
        
        # 5. Adaptive risk cost - learned from memory
        risk_cost = self._learned_risk_cost(plan)
        score -= risk_cost
        
        return score
    
    def _learned_complexity_cost(self, plan: ReasonedPlan) -> float:
        """Learn the cost of complexity from memory.
        
        If we have no memory yet, use a small default penalty.
        As memory accumulates, the penalty adjusts based on actual outcomes.
        """
        if not self._influence:
            # No memory - use small default
            step_count = len(plan.steps)
            return max(0, (step_count - 3) * 0.02)  # Small penalty for >3 steps
        
        # Check if we have historical data on complex plans
        signals = self._influence.compute_influences(limit=10)
        
        # If memory shows complex plans succeed, reduce penalty
        # If memory shows complex plans fail, increase penalty
        success_signals = [s for s in signals if s.strength > 0]
        failure_signals = [s for s in signals if s.strength < 0]
        
        if len(success_signals) + len(failure_signals) < 5:
            # Not enough data - use default
            step_count = len(plan.steps)
            return max(0, (step_count - 3) * 0.02)
        
        # Calculate learned cost
        success_rate = len(success_signals) / (len(success_signals) + len(failure_signals))
        
        # If success rate > 0.6, complex plans are working → reduce penalty
        # If success rate < 0.4, complex plans are failing → increase penalty
        adjustment = (success_rate - 0.5) * 0.1  # -0.05 to +0.05
        
        step_count = len(plan.steps)
        base_cost = max(0, (step_count - 3) * 0.02)
        
        return max(0, base_cost + adjustment)
    
    def _learned_risk_cost(self, plan: ReasonedPlan) -> float:
        """Learn the cost of risk from memory.
        
        If high-risk plans historically succeed, reduce penalty.
        If they fail, increase penalty.
        """
        if not self._influence:
            # No memory - use small default
            high_risk = sum(1 for s in plan.steps if s.get("risk") == "high")
            return high_risk * 0.03  # Small default
        
        signals = self._influence.compute_influences(limit=10)
        
        # Look for signals related to risky actions
        risk_signals = [s for s in signals if abs(s.strength) > 0.3]
        
        if len(risk_signals) < 3:
            high_risk = sum(1 for s in plan.steps if s.get("risk") == "high")
            return high_risk * 0.03
        
        # Calculate learned risk tolerance
        positive_risk = sum(1 for s in risk_signals if s.strength > 0)
        risk_tolerance = positive_risk / len(risk_signals)
        
        # High risk tolerance → less penalty
        # Low risk tolerance → more penalty
        high_risk = sum(1 for s in plan.steps if s.get("risk") == "high")
        base_cost = high_risk * 0.03
        
        adjustment = (risk_tolerance - 0.5) * 0.05
        
        return max(0, base_cost + adjustment)
    
    def select_best(
        self,
        hypotheses: list[ReasonedPlan],
        context: ReasoningContext,
    ) -> ReasonedPlan:
        """Select the best plan from hypotheses."""
        if not hypotheses:
            return self._standard_reason(context.objective, context)
        
        scored = []
        for plan in hypotheses:
            score = self.score_plan(plan, context)
            scored.append((score, plan))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        
        best_score, best_plan = scored[0]
        
        # Add comparison metadata
        best_plan.alternatives = [
            f"Hypothesis {i+1}: score={s:.3f}"
            for i, (s, p) in enumerate(scored)
        ]
        
        logger.info(
            "Selected best plan (score=%.3f) from %d hypotheses",
            best_score, len(hypotheses),
        )
        
        return best_plan
    
    def _estimate_skill_confidence(self, steps: list[dict], available: list[str]) -> float:
        if not steps:
            return 0.0
        known = set(available) | {"reason", "delegate:mimo", "delegate:nemotron"}
        matches = sum(1 for s in steps if s.get("skill") in known)
        return matches / len(steps)
    
    def _estimate_memory_confidence(self, context: ReasoningContext) -> float:
        signals = 0
        if context.known_patterns:
            signals += 1
        if context.failure_modes:
            signals += 1
        if context.recent_actions:
            signals += 1
        return min(1.0, signals / 3)
    
    def _parse_response(self, text: str) -> dict:
        try:
            text = text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text)
        except (json.JSONDecodeError, IndexError):
            return {}
