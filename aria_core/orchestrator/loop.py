from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from ..cognitive import CognitiveEngine, CognitiveState
from ..reasoning import ReasoningEngine, ReasoningContext, ReasonedPlan
from ..skills import SkillManager, SkillResult
from ..reflection import ReflectionEngine, SkillOutcome
from ..learning import LearningEngine, KnowledgeBase
from ..goals import GoalManager, Goal, GoalState
from ..autonomy import TaskRunner, CheckpointStore, RecoveryManager

logger = logging.getLogger("aria.orchestrator")


class LoopPhase(str, Enum):
    IDLE = "idle"
    INSPECT = "inspect"
    REASON = "reason"
    PLAN = "plan"
    EXECUTE = "execute"
    TEST = "test"
    REVIEW = "review"
    REFLECT = "reflect"
    LEARN = "learn"
    STOPPED = "stopped"


@dataclass
class LoopState:
    """State of the autonomous cognitive loop."""
    phase: LoopPhase = LoopPhase.IDLE
    cycle_count: int = 0
    total_successes: int = 0
    total_failures: int = 0
    current_objective: str = ""
    started_at: datetime | None = None
    last_cycle_at: datetime | None = None

    def summary(self) -> str:
        return (
            f"Phase: {self.phase.value} | Cycles: {self.cycle_count} | "
            f"Success: {self.total_successes} | Failures: {self.total_failures}"
        )


class CognitiveLoop:
    """The autonomous cognitive loop that drives ARIA.

    Continuously:
    1. Inspects the environment
    2. Reasons about what to do
    3. Plans actions
    4. Executes skills
    5. Tests results
    6. Reviews outcomes
    7. Reflects on experience
    8. Learns from results
    9. Updates cognitive state

    Runs until stopped by the user or an unrecoverable error.
    """

    def __init__(
        self,
        cognitive: CognitiveEngine,
        skills: SkillManager,
        reflection: ReflectionEngine,
        learning: LearningEngine,
        goals: GoalManager,
        llm: Any = None,
    ):
        self._cognitive = cognitive
        self._skills = skills
        self._reflection = reflection
        self._learning = learning
        self._goals = goals
        self._llm = llm
        self._state = LoopState()
        self._running = False
        self._on_phase: Callable | None = None
        self._on_result: Callable | None = None

    @property
    def state(self) -> LoopState:
        return self._state

    def set_callbacks(self, on_phase: Callable | None = None, on_result: Callable | None = None) -> None:
        self._on_phase = on_phase
        self._on_result = on_result

    def run_objective(self, objective: str) -> dict:
        """Run a single objective through the full cognitive loop."""
        self._state.current_objective = objective
        self._state.cycle_count += 1
        self._state.started_at = self._state.started_at or datetime.now()
        self._state.last_cycle_at = datetime.now()

        result = {
            "objective": objective,
            "success": False,
            "phases": [],
            "duration_ms": 0,
        }

        t0 = time.monotonic()

        try:
            # Phase 1: Inspect
            self._set_phase(LoopPhase.INSPECT)
            context = self._inspect(objective)
            result["phases"].append("inspect")

            # Phase 2: Reason
            self._set_phase(LoopPhase.REASON)
            plan = self._reason(objective, context)
            result["phases"].append("reason")

            # Phase 3: Plan (already done in reason)
            self._set_phase(LoopPhase.PLAN)
            result["phases"].append("plan")

            # Phase 4: Execute
            self._set_phase(LoopPhase.EXECUTE)
            exec_results = self._execute(plan)
            result["phases"].append("execute")

            # Phase 5: Test
            self._set_phase(LoopPhase.TEST)
            test_passed = self._test(exec_results)
            result["phases"].append("test")

            # Phase 6: Review
            self._set_phase(LoopPhase.REVIEW)
            self._review(exec_results, test_passed)
            result["phases"].append("review")

            # Phase 7: Reflect
            self._set_phase(LoopPhase.REFLECT)
            self._reflect(objective, exec_results, test_passed)
            result["phases"].append("reflect")

            # Phase 8: Learn
            self._set_phase(LoopPhase.LEARN)
            self._learn(objective, exec_results, test_passed)
            result["phases"].append("learn")

            result["success"] = test_passed
            if test_passed:
                self._state.total_successes += 1
            else:
                self._state.total_failures += 1

            # Update cognitive state
            self._cognitive.update_from_outcome(
                test_passed,
                context={"objective": objective, "steps": len(plan.steps)},
            )

        except Exception as exc:
            logger.exception("Loop failed for objective: %s", objective)
            result["error"] = str(exc)
            self._state.total_failures += 1
            self._cognitive.update_from_outcome(False, context={"error": str(exc)})

        elapsed = (time.monotonic() - t0) * 1000
        result["duration_ms"] = round(elapsed, 1)

        self._set_phase(LoopPhase.IDLE)
        self._notify_result(result)
        return result

    def _inspect(self, objective: str) -> ReasoningContext:
        """Gather context for reasoning."""
        skill_metas = self._skills.registry.list_skills()
        available = [m.name for m in skill_metas]

        patterns = self._learning.get_successful_strategies(limit=5)
        failures = self._learning.get_failure_modes(limit=5)

        return ReasoningContext(
            objective=objective,
            available_skills=available,
            known_patterns=[p.value for p in patterns],
            failure_modes=[f.value for f in failures],
        )

    def _reason(self, objective: str, context: ReasoningContext) -> ReasonedPlan:
        """Use cognitive engine to reason about the objective."""
        return self._cognitive.reason(objective, context)

    def _execute(self, plan: ReasonedPlan) -> list[dict]:
        """Execute plan steps, collecting results."""
        results = []
        for step in plan.steps:
            skill_name = step.get("skill", "")
            action = step.get("action", "")
            args = step.get("args", {})
            description = step.get("description", "")

            if skill_name.startswith("delegate:"):
                result = SkillResult.ok(output=f"Delegated: {description}")
            elif skill_name == "reason":
                result = SkillResult.ok(output=f"Reasoned: {description}")
            else:
                result = self._execute_skill(skill_name, action, args)

            results.append({
                "step": step,
                "result": result,
                "success": result.success,
            })

            if not result.success:
                break

        return results

    def _execute_skill(self, skill_name: str, action: str, args: dict) -> SkillResult:
        """Execute a single skill."""
        if not skill_name:
            return SkillResult.fail("No skill specified")

        if skill_name == "code" and action in ("scan", "complexity", "structure", "find_patterns"):
            return self._skills.execute_skill(skill_name, action=action, **args)
        elif skill_name == "git":
            return self._skills.execute_skill(skill_name, action=action, **args)
        elif skill_name == "terminal":
            return self._skills.execute_skill(skill_name, command=args.get("command", ""), **{k: v for k, v in args.items() if k != "command"})
        elif skill_name == "file":
            return self._skills.execute_skill(skill_name, action=action, **args)
        elif skill_name == "documentation":
            return self._skills.execute_skill(skill_name, action=action, **args)
        else:
            return self._skills.execute_skill(skill_name, **args)

    def _test(self, exec_results: list[dict]) -> bool:
        """Check if execution succeeded."""
        if not exec_results:
            return False
        return all(r["success"] for r in exec_results)

    def _review(self, exec_results: list[dict], test_passed: bool) -> None:
        """Review execution results."""
        for r in exec_results:
            result = r["result"]
            self._reflection.reflect_skill(SkillOutcome(
                skill_name=r["step"].get("skill", "unknown"),
                action=r["step"].get("action", ""),
                success=result.success,
                duration_ms=result.metadata.get("duration_ms", 0),
                output=str(result.output)[:200] if result.output else "",
                errors=result.errors,
            ))

    def _reflect(self, objective: str, exec_results: list[dict], test_passed: bool) -> None:
        """Reflect on the cycle outcome."""
        action = f"cycle: {objective[:50]}"
        result = "success" if test_passed else f"failed: {len([r for r in exec_results if not r['success']])} steps failed"
        self._reflection.reflect(action, result, {"objective": objective})

    def _learn(self, objective: str, exec_results: list[dict], test_passed: bool) -> None:
        """Learn from the cycle."""
        steps = [r["step"].get("description", "") for r in exec_results]
        self._learning.record_workflow(objective, steps, test_passed)

        for r in exec_results:
            self._learning.record_skill_use(SkillOutcome(
                skill_name=r["step"].get("skill", "unknown"),
                action=r["step"].get("action", ""),
                success=r["success"],
                duration_ms=r["result"].metadata.get("duration_ms", 0),
            ))

    def _set_phase(self, phase: LoopPhase) -> None:
        self._state.phase = phase
        if self._on_phase:
            self._on_phase(phase)
        logger.debug("Phase: %s", phase.value)

    def _notify_result(self, result: dict) -> None:
        if self._on_result:
            self._on_result(result)

    def stop(self) -> None:
        self._running = False
        self._state.phase = LoopPhase.STOPPED

    def get_status(self) -> dict:
        return {
            "loop": self._state.summary(),
            "cognitive": self._cognitive.get_status(),
            "learning": self._learning.get_knowledge_summary(),
        }
