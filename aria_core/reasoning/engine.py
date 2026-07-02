from __future__ import annotations

import json
import logging
from typing import Any, Protocol, runtime_checkable

from .interfaces import ReasoningContext, ReasonedPlan, ConfidenceScore
from ..planning.interfaces import PlanStep

logger = logging.getLogger("aria.reasoning")


@runtime_checkable
class LLMProvider(Protocol):
    def generate(self, prompt: str, *, max_tokens: int = 2048, temperature: float = 0.3) -> Any: ...


REASONING_PROMPT = """You are a reasoning engine for an autonomous engineering system.

OBJECTIVE: {objective}

AVAILABLE SKILLS: {skills}

KNOWN PATTERNS (what has worked before):
{patterns}

KNOWN FAILURE MODES (what to avoid):
{failures}

CONSTRAINTS:
{constraints}

RECENT ACTIONS (avoid repeating):
{recent}

REASONING PROCESS:
1. Understand the objective deeply
2. Identify what information is needed
3. Determine which skills can provide it
4. Consider dependencies between steps
5. Assess risks and failure modes
6. Generate a concrete, actionable plan
7. Assign confidence scores

OUTPUT FORMAT (JSON only):
{{
  "goal": "clear statement of what this plan achieves",
  "steps": [
    {{
      "id": 1,
      "skill": "skill_name",
      "action": "specific action",
      "args": {{"key": "value"}},
      "description": "what this step accomplishes",
      "dependencies": [],
      "confidence": 0.95,
      "risk": "low|medium|high",
      "rationale": "why this step is necessary"
    }}
  ],
  "overall_confidence": 0.90,
  "risks": ["list of risks"],
  "alternatives": ["alternative approaches considered"],
  "reasoning": "brief summary of reasoning process"
}}

RULES:
- Each step must use a real skill name from the available list
- Steps must be concrete and executable
- Dependencies reference step IDs
- Be specific about args (paths, commands, patterns)
- If uncertain, lower confidence — don't guess
- Consider the most efficient path
"""

VERIFICATION_PROMPT = """Verify this plan before execution.

OBJECTIVE: {objective}
PLAN: {plan}

Check:
1. Are all dependencies satisfied?
2. Are all skills available?
3. Are there circular dependencies?
4. Are permissions sufficient?
5. Is there a cheaper/faster path?
6. Are there unconsidered risks?

Respond with JSON:
{{
  "verified": true/false,
  "issues": ["list of issues found"],
  "suggestions": ["improvement suggestions"],
  "adjusted_steps": [] // only if changes needed
}}
"""


class ReasoningEngine:
    """Cognitive reasoning pipeline that replaces keyword-based planning.

    Gathers context → reasons about approach → produces structured plan →
    verifies plan → returns verified plan with confidence scores.
    """

    def __init__(self, llm: LLMProvider | None = None):
        self._llm = llm

    def reason(self, objective: str, context: ReasoningContext | None = None) -> ReasonedPlan:
        """Full reasoning pipeline: gather context → reason → verify → return plan."""
        if context is None:
            context = ReasoningContext(objective=objective)

        if self._llm is None:
            return self._fallback_reason(objective, context)

        plan = self._reason_with_llm(objective, context)
        plan = self._verify_plan(plan, context.available_skills)
        return plan

    def _reason_with_llm(self, objective: str, context: ReasoningContext) -> ReasonedPlan:
        prompt = REASONING_PROMPT.format(
            objective=objective,
            skills=", ".join(context.available_skills) or "(none registered)",
            patterns="\n".join(f"- {p}" for p in context.known_patterns) or "(none)",
            failures="\n".join(f"- {f}" for f in context.failure_modes) or "(none)",
            constraints="\n".join(f"- {c}" for c in context.constraints) or "(none)",
            recent="\n".join(f"- {a}" for a in context.recent_actions) or "(none)",
        )

        try:
            resp = self._llm.generate(prompt, max_tokens=3000, temperature=0.3)
            text = resp.text if hasattr(resp, "text") else str(resp)
            data = self._parse_response(text)

            if not data:
                return self._fallback_reason(objective, context)

            steps = []
            for s in data.get("steps", []):
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
                goal=min(1.0, data.get("overall_confidence", 0.7) + 0.1),
                plan=data.get("overall_confidence", 0.7),
                skill_selection=self._estimate_skill_confidence(steps, context.available_skills),
                memory_match=self._estimate_memory_confidence(context),
            )

            return ReasonedPlan(
                objective=objective,
                steps=steps,
                confidence=confidence,
                reasoning=data.get("reasoning", ""),
                risks=data.get("risks", []),
                alternatives=data.get("alternatives", []),
            )
        except Exception as exc:
            logger.warning("LLM reasoning failed: %s", exc)
            return self._fallback_reason(objective, context)

    def _verify_plan(self, plan: ReasonedPlan, available_skills: list[str] | None = None) -> ReasonedPlan:
        """Verify a plan before execution."""
        issues = []
        notes = []

        known = set(available_skills or []) | {"reason", "delegate:mimo", "delegate:nemotron"}
        skills_used = {s.get("skill") for s in plan.steps}
        unknown = skills_used - known
        if unknown:
            issues.append(f"Unknown skills: {unknown}")

        step_ids = {s.get("id") for s in plan.steps}
        for step in plan.steps:
            for dep in step.get("dependencies", []):
                if dep not in step_ids:
                    issues.append(f"Step {step.get('id')} depends on non-existent step {dep}")

        dep_graph = {s.get("id"): s.get("dependencies", []) for s in plan.steps}
        if self._has_cycle(dep_graph):
            issues.append("Circular dependency detected")

        for step in plan.steps:
            if step.get("confidence", 1.0) < 0.3:
                issues.append(f"Step {step.get('id')} has very low confidence ({step.get('confidence')})")

        if not plan.steps:
            issues.append("Plan has no steps")

        notes.append(f"Plan has {len(plan.steps)} steps")
        if plan.confidence.is_confident:
            notes.append(f"Confidence is acceptable ({plan.confidence.overall:.0%})")
        else:
            notes.append(f"Confidence is low ({plan.confidence.overall:.0%}) — review carefully")

        plan.verified = len(issues) == 0
        plan.verification_notes = issues + notes
        return plan

    def replan_from_failure(self, original: ReasonedPlan, failed_step: dict, error: str) -> ReasonedPlan:
        """Replan from a failed step without restarting."""
        completed_ids = set()
        for step in original.steps:
            if step.get("status") == "completed":
                completed_ids.add(step.get("id"))

        remaining_steps = [
            s for s in original.steps
            if s.get("id") not in completed_ids and s.get("id") != failed_step.get("id")
        ]

        if self._llm is not None:
            return self._replan_with_llm(original, failed_step, error, remaining_steps)

        for step in remaining_steps:
            deps = step.get("dependencies", [])
            step["dependencies"] = [d for d in deps if d in completed_ids]

        return ReasonedPlan(
            objective=original.objective,
            steps=remaining_steps,
            confidence=ConfidenceScore(
                goal=original.confidence.goal * 0.9,
                plan=original.confidence.plan * 0.9,
                skill_selection=original.confidence.skill_selection,
                memory_match=original.confidence.memory_match,
            ),
            reasoning=f"Replanned after step {failed_step.get('id')} failed: {error}",
            risks=original.risks + [f"Previous failure: {error}"],
        )

    def _replan_with_llm(self, original: ReasonedPlan, failed_step: dict, error: str, remaining: list[dict]) -> ReasonedPlan:
        prompt = (
            f"A plan step failed. Replan from this point.\n\n"
            f"Original objective: {original.objective}\n"
            f"Failed step: {json.dumps(failed_step)}\n"
            f"Error: {error}\n"
            f"Remaining steps: {json.dumps(remaining)}\n\n"
            f"Respond with JSON: {{\"steps\": [...], \"reasoning\": \"...\", \"risks\": [...]}}\n"
            f"Use the same format as before."
        )

        try:
            resp = self._llm.generate(prompt, max_tokens=2000, temperature=0.3)
            text = resp.text if hasattr(resp, "text") else str(resp)
            data = self._parse_response(text)

            if data and "steps" in data:
                return ReasonedPlan(
                    objective=original.objective,
                    steps=data["steps"],
                    confidence=ConfidenceScore(
                        goal=original.confidence.goal * 0.85,
                        plan=0.6,
                        skill_selection=original.confidence.skill_selection,
                        memory_match=original.confidence.memory_match,
                    ),
                    reasoning=data.get("reasoning", f"Replanned after failure: {error}"),
                    risks=data.get("risks", []) + [f"Previous failure: {error}"],
                )
        except Exception as exc:
            logger.warning("LLM replan failed: %s", exc)

        return self.replan_from_failure.__wrapped__(self, original, failed_step, error) if hasattr(self.replan_from_failure, "__wrapped__") else ReasonedPlan(
            objective=original.objective,
            steps=remaining,
            confidence=ConfidenceScore(goal=0.5, plan=0.5, skill_selection=0.5, memory_match=0.5),
            reasoning=f"Fallback replan after failure: {error}",
        )

    def _fallback_reason(self, objective: str, context: ReasoningContext) -> ReasonedPlan:
        """Keyword-based fallback when LLM is unavailable."""
        obj = objective.lower()
        steps = []

        if any(w in obj for w in ["read", "inspect", "examine", "check", "analyze"]):
            steps.append({"id": 1, "skill": "code", "action": "scan", "args": {"path": "."},
                         "description": "Scan repository", "dependencies": [], "confidence": 0.8, "risk": "low"})

        if any(w in obj for w in ["test", "fix", "bug", "fail", "error"]):
            steps.append({"id": len(steps) + 1, "skill": "terminal", "action": "run",
                         "args": {"command": "python -m pytest tests/ -q --tb=short 2>&1"},
                         "description": "Run tests", "dependencies": [len(steps)], "confidence": 0.7, "risk": "low"})

        if any(w in obj for w in ["todo", "debt", "improve", "refactor"]):
            steps.append({"id": len(steps) + 1, "skill": "code", "action": "find_patterns",
                         "args": {"pattern": "TODO|FIXME|HACK|XXX", "path": "."},
                         "description": "Find technical debt", "dependencies": [], "confidence": 0.8, "risk": "low"})

        if any(w in obj for w in ["git", "commit", "status"]):
            steps.append({"id": len(steps) + 1, "skill": "git", "action": "status",
                         "args": {}, "description": "Check git status", "dependencies": [], "confidence": 0.9, "risk": "low"})

        if any(w in obj for w in ["create", "write", "build", "generate"]):
            steps.append({"id": len(steps) + 1, "skill": "code", "action": "structure",
                         "args": {"path": "."}, "description": "Analyze structure",
                         "dependencies": [], "confidence": 0.7, "risk": "low"})

        if any(w in obj for w in ["documentation", "readme", "docs"]):
            steps.append({"id": len(steps) + 1, "skill": "documentation", "action": "list_docs",
                         "args": {}, "description": "List documentation", "dependencies": [], "confidence": 0.8, "risk": "low"})

        if any(w in obj for w in ["complexity", "quality", "review"]):
            steps.append({"id": len(steps) + 1, "skill": "code", "action": "complexity",
                         "args": {"path": "."}, "description": "Analyze complexity",
                         "dependencies": [], "confidence": 0.7, "risk": "low"})

        if not steps:
            steps.append({"id": 1, "skill": "code", "action": "scan",
                         "args": {"path": "."}, "description": "Scan repository",
                         "dependencies": [], "confidence": 0.6, "risk": "low"})

        confidence = ConfidenceScore(
            goal=0.6,
            plan=0.5,
            skill_selection=0.7,
            memory_match=0.3,
        )

        return ReasonedPlan(
            objective=objective,
            steps=steps,
            confidence=confidence,
            reasoning="Keyword-based fallback (no LLM available)",
            risks=["No LLM reasoning — plan may not be optimal"],
        )

    def _estimate_skill_confidence(self, steps: list[dict], available: list[str]) -> float:
        if not steps:
            return 0.0
        known = set(available) | {"reason", "delegate:mimo", "delegate:nemotron"}
        matches = sum(1 for s in steps if s.get("skill") in known)
        return matches / len(steps) if steps else 0.0

    def _estimate_memory_confidence(self, context: ReasoningContext) -> float:
        signals = 0
        if context.known_patterns:
            signals += 1
        if context.failure_modes:
            signals += 1
        if context.recent_actions:
            signals += 1
        return min(1.0, signals / 3)

    def _has_cycle(self, graph: dict) -> bool:
        visited = set()
        path = set()

        def dfs(node):
            if node in path:
                return True
            if node in visited:
                return False
            visited.add(node)
            path.add(node)
            for dep in graph.get(node, []):
                if dfs(dep):
                    return True
            path.remove(node)
            return False

        for node in graph:
            if dfs(node):
                return True
        return False

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
