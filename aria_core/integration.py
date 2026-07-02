from __future__ import annotations

import logging
import time
from typing import Any, Callable

from .goals import Goal, GoalManager, GoalState
from .planning import PlanningEngine, Plan, PlanStep
from .reflection import ReflectionEngine, SkillOutcome, ReflectionSummary
from .learning import LearningEngine, DecisionInfluencer, KnowledgeBase
from .skills import SkillManager, SkillResult
from .autonomy import TaskRunner, Task, TaskState, TaskResult, CheckpointStore, RecoveryManager

logger = logging.getLogger("aria.integration")


class ARIACore:
    """The central integration point for all ARIA modules.

    Connects: Goals → Planning → Skills → Reflection → Learning
    Provides a single interface for the Language Cortex to interact with.
    """

    def __init__(self, llm: Any = None, db_path: str | None = None):
        self._llm = llm
        self._db_path = db_path

        self.goals = GoalManager()
        self.planning = PlanningEngine(llm=llm)
        self.reflection = ReflectionEngine(llm=llm)
        self.knowledge = KnowledgeBase(db_path=db_path)
        self.learning = LearningEngine(knowledge=self.knowledge, reflection=self.reflection)
        self.influencer = DecisionInfluencer(self.learning)
        self.skills = SkillManager()
        self.checkpoint = CheckpointStore(db_path=db_path)
        self.runner = TaskRunner(checkpoint_store=self.checkpoint)
        self.recovery = RecoveryManager(self.runner)

        self._cycle_count = 0
        logger.info("ARIACore initialized")

    def process_objective(self, objective: str) -> dict:
        """Process a high-level objective through the full pipeline.

        Returns a summary of what was planned, executed, and learned.
        """
        t0 = time.monotonic()
        self._cycle_count += 1

        # 1. Learn from past experience
        self.learning.learn_from_reflections()
        self.learning.learn_from_skill_stats()

        # 2. Get knowledge context
        context = self.influencer.get_context_for_task(objective)
        knowledge_prompt = self.influencer.build_recommendation_prompt(objective)

        # 3. Create goal
        goal = Goal(description=objective, priority=1.0)
        self.goals.add_goal(goal)

        # 4. Create plan
        plan = self.planning.create_plan(objective)

        # 5. Execute plan steps
        results = []
        for step in plan.steps:
            step_result = self._execute_step(step)
            results.append(step_result)

            if step_result.success:
                self.planning.step_completed(plan.id, step.id, str(step_result.output)[:200])
            else:
                self.planning.step_failed(plan.id, step.id, step_result.error)
                break

        # 6. Reflect on outcomes
        success = all(r.success for r in results)
        self.reflection.reflect(
            action=f"process_objective: {objective[:50]}",
            result="success" if success else f"failed: {results[-1].error if results else 'no results'}",
            context={"objective": objective, "steps": len(plan.steps)},
        )

        # 7. Learn from this cycle
        self.learning.learn_workflow(objective, [s.description for s in plan.steps], success)

        # 8. Update goal
        if success:
            self.goals.complete_goal(goal.id)
        else:
            self.goals.block_goal(goal.id, "execution failed")

        elapsed = (time.monotonic() - t0) * 1000

        summary = {
            "objective": objective,
            "success": success,
            "plan_steps": len(plan.steps),
            "steps_completed": sum(1 for r in results if r.success),
            "duration_ms": round(elapsed, 1),
            "goal_id": goal.id,
            "plan_id": plan.id,
            "knowledge_context": context,
        }

        logger.info(
            "Objective processed: %s (success=%s, %.0fms)",
            objective[:50], success, elapsed,
        )
        return summary

    def _execute_step(self, step: PlanStep) -> SkillResult:
        """Execute a single plan step using the appropriate skill."""
        action = step.action

        if action.startswith("delegate:"):
            specialist = action.split(":", 1)[1]
            return SkillResult.ok(
                output=f"Delegated to {specialist}: {step.description}",
                delegated=True,
                specialist=specialist,
            )

        if action == "reason":
            return SkillResult.ok(output=f"Reasoned about: {step.description}")

        return self.skills.execute_skill(action, **step.args)

    def get_status(self) -> dict:
        """Get a comprehensive status of all ARIA systems."""
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
                "summary": self.skills.summary(),
            },
            "reflection": self.reflection.summarize(),
            "tasks": {
                "resumable": len(self.runner.get_resumable_tasks()),
                "recovery": self.recovery.summarize_recovery_status(),
            },
        }

    def shutdown(self) -> None:
        """Clean up all resources."""
        self.knowledge.close()
        self.checkpoint.close()
        logger.info("ARIACore shut down")
