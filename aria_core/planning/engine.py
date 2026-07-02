from __future__ import annotations

import json
import logging
from typing import Any, Protocol, runtime_checkable

from .interfaces import Plan, PlanStep, PlanStepState

logger = logging.getLogger("aria.planning")


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal interface for LLM calls."""
    def generate(self, prompt: str, *, max_tokens: int = 2048, temperature: float = 0.3) -> Any: ...


PLAN_PROMPT = """You are a planning engine. Break the objective into concrete, ordered steps.

Objective: {objective}

Available tools: {tools}

Respond with a JSON array of steps:
[
  {{
    "description": "what this step accomplishes",
    "action": "tool_name or 'delegate:mimo' or 'delegate:nemotron' or 'reason'",
    "args": {{}},
    "depends_on": []
  }}
]

Rules:
- Each step must be concrete and actionable
- Use depends_on to order steps (list of step indices, 0-based)
- Use "delegate:mimo" for architecture/implementation tasks
- Use "delegate:nemotron" for testing/validation tasks
- Use "reason" for analysis or planning steps
- Keep steps small — each should be completable in one action
- Return ONLY the JSON array, no other text
"""


class PlanningEngine:
    """Breaks objectives into ordered, actionable plans.

    Uses LLM to decompose objectives, then manages execution
    through the plan's step lifecycle.
    """

    def __init__(self, llm: LLMProvider | None = None, tools: list[str] | None = None):
        self._llm = llm
        self._tools = tools or []
        self._plans: dict[str, Plan] = {}

    def create_plan(self, objective: str) -> Plan:
        """Create a plan from an objective. Uses LLM if available, else stubs."""
        if self._llm is not None:
            steps = self._decompose_with_llm(objective)
        else:
            steps = self._decompose_stub(objective)

        plan = Plan(objective=objective, steps=steps)
        self._plans[plan.id] = plan
        logger.info("Created plan %s with %d steps for: %s", plan.id, len(steps), objective[:80])
        return plan

    def get_plan(self, plan_id: str) -> Plan | None:
        return self._plans.get(plan_id)

    def list_plans(self) -> list[Plan]:
        return list(self._plans.values())

    def step_completed(self, plan_id: str, step_id: str, result: str = "") -> None:
        plan = self._plans.get(plan_id)
        if plan is None:
            return
        for step in plan.steps:
            if step.id == step_id:
                step.state = PlanStepState.COMPLETED
                step.result = result
                step.completed_at = __import__("datetime").datetime.now()
                break
        plan.updated_at = __import__("datetime").datetime.now()
        if plan.is_complete:
            plan.completed_at = __import__("datetime").datetime.now()

    def step_failed(self, plan_id: str, step_id: str, reason: str = "") -> None:
        plan = self._plans.get(plan_id)
        if plan is None:
            return
        for step in plan.steps:
            if step.id == step_id:
                step.state = PlanStepState.FAILED
                step.result = reason
                break
        plan.updated_at = __import__("datetime").datetime.now()

    def _decompose_with_llm(self, objective: str) -> list[PlanStep]:
        prompt = PLAN_PROMPT.format(
            objective=objective,
            tools=", ".join(self._tools) if self._tools else "(no tools specified)",
        )
        try:
            resp = self._llm.generate(prompt, max_tokens=2048, temperature=0.3)
            text = resp.text if hasattr(resp, "text") else str(resp)
            steps_data = self._parse_steps(text)
            if not steps_data:
                return self._decompose_stub(objective)
            return [
                PlanStep(
                    description=s.get("description", ""),
                    action=s.get("action", "reason"),
                    args=s.get("args", {}),
                    depends_on=[
                        str(i) for i in s.get("depends_on", [])
                    ],
                )
                for s in steps_data
            ]
        except Exception as exc:
            logger.warning("LLM decomposition failed: %s", exc)
            return self._decompose_stub(objective)

    def _decompose_stub(self, objective: str) -> list[PlanStep]:
        """Keyword-based fallback that produces real action plans."""
        obj = objective.lower()
        steps = []

        if any(w in obj for w in ["read", "inspect", "examine", "look", "check"]):
            steps.append(PlanStep(description="Scan repository structure", action="code", args={"action": "scan", "path": "."}))
            if any(w in obj for w in ["file", "code", "source", "module"]):
                steps.append(PlanStep(description="Analyze code complexity", action="code", args={"action": "complexity", "path": "."}))

        if any(w in obj for w in ["test", "fix", "bug", "fail", "error"]):
            steps.append(PlanStep(description="Run test suite", action="terminal", args={"command": "python -m pytest tests/ -q --tb=short 2>&1"}))

        if any(w in obj for w in ["todo", "debt", "improve", "refactor"]):
            steps.append(PlanStep(description="Find TODOs and technical debt", action="code", args={"action": "find_patterns", "pattern": "TODO|FIXME|HACK|XXX", "path": "."}))

        if any(w in obj for w in ["git", "commit", "status"]):
            steps.append(PlanStep(description="Check git status", action="git", args={"action": "status"}))

        if any(w in obj for w in ["create", "write", "build", "generate", "new"]):
            steps.append(PlanStep(description="Scan existing structure", action="code", args={"action": "structure", "path": "."}))

        if any(w in obj for w in ["analyze", "analysis", "review", "audit"]):
            steps.append(PlanStep(description="Analyze codebase structure", action="code", args={"action": "structure", "path": "."}))
            steps.append(PlanStep(description="Analyze code complexity", action="code", args={"action": "complexity", "path": "."}))

        if any(w in obj for w in ["documentation", "readme", "docs"]):
            steps.append(PlanStep(description="List existing documentation", action="documentation", args={"action": "list_docs"}))

        if any(w in obj for w in ["run", "execute", "command"]):
            steps.append(PlanStep(description="Execute command", action="terminal", args={"command": "echo 'executed'"}))

        if not steps:
            steps.append(PlanStep(description="Scan repository", action="code", args={"action": "scan", "path": "."}))

        return steps

    def _parse_steps(self, text: str) -> list[dict]:
        try:
            text = text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            data = json.loads(text)
            if isinstance(data, list):
                return data
            return []
        except (json.JSONDecodeError, IndexError):
            logger.warning("Failed to parse plan steps from LLM output")
            return []
