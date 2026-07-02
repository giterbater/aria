from __future__ import annotations

import logging
import time
from typing import Any

from .goals import Goal, GoalManager, GoalState
from .reasoning import ReasoningEngine, ReasoningContext, ReasonedPlan, ConfidenceScore
from .reflection import ReflectionEngine, SkillOutcome
from .learning import LearningEngine, DecisionInfluencer, KnowledgeBase
from .skills import SkillManager, SkillResult
from .autonomy import TaskRunner, Task, TaskState, TaskResult, CheckpointStore, RecoveryManager

logger = logging.getLogger("aria.integration")


class ARIACore:
    """The central integration point for all ARIA modules.

    Uses a reasoning pipeline instead of keyword matching:
    Objective → Context → LLM Reasoning → Verified Plan → Execute → Reflect → Learn
    """

    def __init__(self, llm: Any = None, db_path: str | None = None):
        self._llm = llm
        self._db_path = db_path

        self.goals = GoalManager()
        self.reasoning = ReasoningEngine(llm=llm)
        self.reflection = ReflectionEngine(llm=llm)
        self.knowledge = KnowledgeBase(db_path=db_path)
        self.learning = LearningEngine(knowledge=self.knowledge, reflection=self.reflection)
        self.influencer = DecisionInfluencer(self.learning)
        self.skills = SkillManager()
        self.checkpoint = CheckpointStore(db_path=db_path)
        self.runner = TaskRunner(checkpoint_store=self.checkpoint)
        self.recovery = RecoveryManager(self.runner)

        self._cycle_count = 0
        self._history: list[dict] = []
        logger.info("ARIACore initialized")

    def process_objective(self, objective: str) -> dict:
        """Full reasoning pipeline: context → reason → verify → execute → reflect → learn."""
        t0 = time.monotonic()
        self._cycle_count += 1

        # 1. Learn from past experience
        self.learning.learn_from_reflections()
        self.learning.learn_from_skill_stats()

        # 2. Gather context
        context = self._gather_context(objective)

        # 3. Reason about the objective
        plan = self.reasoning.reason(objective, context)

        # 4. Create goal
        goal = Goal(description=objective, priority=1.0)
        self.goals.add_goal(goal)

        # 5. Execute plan steps with adaptive replanning
        results = []
        failed_step = None
        for step in plan.steps:
            if step.get("status") == "completed":
                continue

            step_result = self._execute_step(step)
            results.append({"step": step, "result": step_result})

            if step_result.success:
                step["status"] = "completed"
            else:
                step["status"] = "failed"
                failed_step = step
                break

        # 6. Adaptive replanning if a step failed
        if failed_step and failed_step.get("confidence", 1.0) > 0.5:
            error_msg = "; ".join(step_result.errors) if step_result.errors else "step failed"
            replan = self.reasoning.replan_from_failure(plan, failed_step, error_msg)
            for step in replan.steps:
                if step.get("status") != "completed":
                    step_result = self._execute_step(step)
                    results.append({"step": step, "result": step_result})
                    step["status"] = "completed" if step_result.success else "failed"

        # 7. Reflect on outcomes
        success = all(r["result"].success for r in results)
        self.reflection.reflect(
            action=f"process_objective: {objective[:50]}",
            result="success" if success else "failed",
            context={"objective": objective, "steps": len(plan.steps),
                     "confidence": plan.confidence.overall},
        )

        # 8. Learn from this cycle
        self.learning.learn_workflow(objective, [s.get("description", "") for s in plan.steps], success)

        # 9. Update goal
        if success:
            self.goals.complete_goal(goal.id)
        else:
            self.goals.block_goal(goal.id, "execution failed")

        elapsed = (time.monotonic() - t0) * 1000

        summary = {
            "objective": objective,
            "success": success,
            "plan_steps": len(plan.steps),
            "steps_completed": sum(1 for r in results if r["result"].success),
            "duration_ms": round(elapsed, 1),
            "confidence": plan.confidence.summary(),
            "verified": plan.verified,
            "verification_notes": plan.verification_notes,
            "risks": plan.risks,
            "reasoning": plan.reasoning,
        }

        self._history.append(summary)
        logger.info(
            "Objective: %s (success=%s, confidence=%.0f%%, %.0fms)",
            objective[:50], success, plan.confidence.overall * 100, elapsed,
        )
        return summary

    def _gather_context(self, objective: str) -> ReasoningContext:
        """Gather all context for reasoning."""
        skill_metas = self.skills.registry.list_skills()
        available_skills = [m.name for m in skill_metas]

        patterns = self.learning.get_successful_strategies(limit=5)
        failure_modes = self.learning.get_failure_modes(limit=5)
        recent = self._history[-5:]

        influencer_context = self.influencer.get_context_for_task(objective)

        return ReasoningContext(
            objective=objective,
            available_skills=available_skills,
            known_patterns=[p.value for p in patterns],
            failure_modes=[f.value for f in failure_modes],
            recent_actions=[f"{'OK' if h['success'] else 'FAIL'}: {h['objective'][:50]}" for h in recent],
            active_goals=[g.description for g in self.goals.list_goals(GoalState.ACTIVE)],
            constraints=influencer_context.get("warnings", []),
        )

    def _execute_step(self, step: dict) -> SkillResult:
        """Execute a single plan step."""
        skill_name = step.get("skill", "")
        action = step.get("action", "")
        args = step.get("args", {})

        if skill_name.startswith("delegate:"):
            specialist = skill_name.split(":", 1)[1]
            return SkillResult.ok(output=f"Delegated to {specialist}: {step.get('description', '')}")

        if skill_name == "reason":
            return SkillResult.ok(output=f"Reasoned about: {step.get('description', '')}")

        if skill_name and action:
            if skill_name == "code" and action in ("scan", "complexity", "structure", "find_patterns"):
                return self.skills.execute_skill(skill_name, action=action, **args)
            elif skill_name == "git":
                return self.skills.execute_skill(skill_name, action=action, **args)
            elif skill_name == "terminal":
                return self.skills.execute_skill(skill_name, command=args.get("command", ""), **{k: v for k, v in args.items() if k != "command"})
            elif skill_name == "file":
                return self.skills.execute_skill(skill_name, action=action, **args)
            elif skill_name == "documentation":
                return self.skills.execute_skill(skill_name, action=action, **args)
            else:
                return self.skills.execute_skill(skill_name, **args)

        return SkillResult.fail(f"Cannot execute step: skill={skill_name}, action={action}")

    def get_status(self) -> dict:
        """Comprehensive status of all ARIA systems."""
        return {
            "cycle_count": self._cycle_count,
            "goals": {
                "active": len(self.goals.list_goals(GoalState.ACTIVE)),
                "completed": len(self.goals.list_goals(GoalState.COMPLETED)),
                "overall_progress": self.goals.overall_progress(),
            },
            "knowledge": {
                "total": self.knowledge.count(),
                "by_type": self.knowledge.count_by_type(),
            },
            "skills": {
                "registered": self.skills.registry.count,
                "history": len(self.skills.get_history()),
            },
            "reflection": self.reflection.summarize(),
            "tasks": {
                "resumable": len(self.runner.get_resumable_tasks()),
            },
        }

    def shutdown(self) -> None:
        self.knowledge.close()
        self.checkpoint.close()
        logger.info("ARIACore shut down")
