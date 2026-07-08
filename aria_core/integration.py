from __future__ import annotations

import logging
import time
from typing import Any

from .goals import Goal, GoalManager, GoalState
from .reasoning import ReasoningEngine, ReasoningContext, ReasonedPlan, ConfidenceScore
from .reflection import ReflectionEngine, SkillOutcome
from .learning import LearningEngine, DecisionInfluencer, KnowledgeBase
from .skills import SkillManager, SkillResult
from .memory.models import EpisodicItem, Outcome
from .memory.sqlite_memory_system import SQLiteMemorySystem
from .memory.influence import MemoryInfluenceEngine
from .identity.formation import IdentityFormationEngine, IdentityDimension
from .values.formation import ValueFormationEngine, ValueType
from .planning import PlanStep
from .planning.interfaces import PlanStepState
from .autonomy import TaskRunner, Task, TaskState, TaskResult, CheckpointStore, RecoveryManager

logger = logging.getLogger("aria.integration")


class ARIACore:
    """The central integration point for all ARIA modules.

    Uses a reasoning pipeline instead of keyword matching:
    Objective → Context → LLM Reasoning → Verified Plan → Execute → Reflect → Learn

    Developmental components:
    - MemoryInfluenceEngine: memory shapes future decisions
    - IdentityFormationEngine: identity emerges from experience
    - ValueFormationEngine: values emerge from outcomes
    """

    def __init__(self, llm: Any = None, db_path: str | None = None):
        self._llm = llm
        self._db_path = db_path

        self.goals = GoalManager()
        self.memory = SQLiteMemorySystem(db_path or ":memory:")
        self.reasoning = ReasoningEngine(llm=llm, memory=self.memory)
        self.reflection = ReflectionEngine(llm=llm)
        self.knowledge = KnowledgeBase(db_path=db_path)
        self.learning = LearningEngine(knowledge=self.knowledge, reflection=self.reflection)
        self.influencer = DecisionInfluencer(self.learning)
        self.skills = SkillManager(auto_register_builtins=True, base_path=".")
        self.checkpoint = CheckpointStore(db_path=db_path)
        self.runner = TaskRunner(checkpoint_store=self.checkpoint)
        self.recovery = RecoveryManager(self.runner)

        # Developmental engines
        self.memory_influence = MemoryInfluenceEngine(self.memory)
        self.identity = IdentityFormationEngine()
        self.values = ValueFormationEngine()

        self._cycle_count = 0
        self._history: list[dict] = []
        logger.info("ARIACore initialized with developmental engines")

    def process_objective(self, objective: str) -> dict:
        """Full reasoning pipeline: context → reason → verify → execute → reflect → learn."""
        t0 = time.monotonic()
        self._cycle_count += 1

        # 1. Learn from past experience
        self.learning.learn_from_reflections()
        self.learning.learn_from_skill_stats()

        # 2. Gather context
        context = self._gather_context(objective)

        # 3. Reason about the objective, then adapt into typed execution state.
        reasoned_plan = self.reasoning.reason(objective, context)
        plan = reasoned_plan.to_plan()

        # 4. Create goal
        goal = Goal(description=objective, priority=1.0)
        self.goals.add_goal(goal)

        # 5. Execute plan steps with adaptive replanning
        results = []
        failed_step = None
        raw_by_id = {str(s.get("id")): s for s in reasoned_plan.steps}
        while True:
            step = plan.next_step
            if step is None:
                break

            step.state = PlanStepState.IN_PROGRESS
            step_result = self._execute_step(step)
            self._record_step_feedback(step, step_result)
            results.append({"step": step, "result": step_result})

            if step_result.success:
                step.state = PlanStepState.COMPLETED
                step.result = str(step_result.output or "")
                raw_step = raw_by_id.get(step.id)
                if raw_step is not None:
                    raw_step["status"] = "completed"
            else:
                step.state = PlanStepState.FAILED
                step.result = "; ".join(step_result.errors) if step_result.errors else "step failed"
                raw_step = raw_by_id.get(step.id)
                if raw_step is not None:
                    raw_step["status"] = "failed"
                failed_step = step
                break

        # 6. Adaptive replanning if a step failed
        failed_raw = raw_by_id.get(failed_step.id) if failed_step is not None else None
        failed_confidence = failed_raw.get("confidence", 1.0) if failed_raw is not None else 1.0
        if failed_step and failed_confidence > 0.5:
            error_msg = "; ".join(results[-1]["result"].errors) if results[-1]["result"].errors else "step failed"
            replan = self.reasoning.replan_from_failure(reasoned_plan, failed_raw or {"id": failed_step.id}, error_msg)
            replan_plan = replan.to_plan()
            while True:
                step = replan_plan.next_step
                if step is None:
                    break

                step.state = PlanStepState.IN_PROGRESS
                step_result = self._execute_step(step)
                self._record_step_feedback(step, step_result)
                results.append({"step": step, "result": step_result})
                if step_result.success:
                    step.state = PlanStepState.COMPLETED
                    step.result = str(step_result.output or "")
                else:
                    step.state = PlanStepState.FAILED
                    step.result = "; ".join(step_result.errors) if step_result.errors else "step failed"
                    break

        # 7. Reflect on outcomes
        success = bool(results) and all(r["result"].success for r in results)
        self.reflection.reflect(
            action=f"process_objective: {objective[:50]}",
            result="success" if success else "failed",
            context={"objective": objective, "steps": len(plan.steps),
                     "confidence": reasoned_plan.confidence.overall},
        )

        # 8. Learn from this cycle
        self.learning.record_workflow(objective, [s.description for s in plan.steps], success)

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
            "confidence": reasoned_plan.confidence.summary(),
            "verified": reasoned_plan.verified,
            "verification_notes": reasoned_plan.verification_notes,
            "risks": reasoned_plan.risks,
            "reasoning": reasoned_plan.reasoning,
        }

        self._history.append(summary)
        logger.info(
            "Objective: %s (success=%s, confidence=%.0f%%, %.0fms)",
            objective[:50], success, reasoned_plan.confidence.overall * 100, elapsed,
        )
        return summary

    def _gather_context(self, objective: str) -> ReasoningContext:
        """Gather all context for reasoning, including developmental signals."""
        skill_metas = self.skills.registry.list_skills()
        available_skills = [m.name for m in skill_metas]

        patterns = self.learning.get_successful_strategies(limit=5)
        failure_modes = self.learning.get_failure_modes(limit=5)
        recent = self._history[-5:]

        influencer_context = self.influencer.get_context_for_task(objective)

        # Gather developmental context
        identity_signals = self.identity.get_identity_signals()
        value_signals = self.values.get_value_signals()
        memory_influences = self.memory_influence.get_influence_summary()

        # Build enhanced constraints from developmental signals
        constraints = list(influencer_context.get("warnings", []))

        # Add identity-based recommendations
        if identity_signals.get('recommendations'):
            constraints.extend(identity_signals['recommendations'])

        # Add value-based recommendations
        if value_signals.get('recommendations'):
            constraints.extend(value_signals['recommendations'])

        # Add memory influence patterns
        if memory_influences.get('top_patterns'):
            for pattern in memory_influences['top_patterns'][:3]:
                constraints.append(f"Pattern: {pattern['pattern']}")

        return ReasoningContext(
            objective=objective,
            available_skills=available_skills,
            known_patterns=[p.value for p in patterns],
            failure_modes=[f.value for f in failure_modes],
            recent_actions=[f"{'OK' if h['success'] else 'FAIL'}: {h['objective'][:50]}" for h in recent],
            active_goals=[g.description for g in self.goals.list_goals(GoalState.ACTIVE)],
            constraints=constraints,
        )

    def _execute_step(self, step: PlanStep | dict) -> SkillResult:
        """Execute a single typed plan step.

        Dict input is accepted as a compatibility shim for older callers.
        """
        if isinstance(step, dict):
            step = ReasonedPlan(steps=[step]).to_plan().steps[0]

        skill_name = step.action
        args = dict(step.args)
        action = args.pop("action", "")

        if skill_name.startswith("delegate:"):
            specialist = skill_name.split(":", 1)[1]
            return SkillResult.ok(output=f"Delegated to {specialist}: {step.description}")

        if skill_name == "reason":
            return SkillResult.ok(output=f"Reasoned about: {step.description}")

        if skill_name == "terminal":
            return self.skills.execute_skill(
                skill_name,
                command=args.get("command", ""),
                **{k: v for k, v in args.items() if k != "command"},
            )

        if skill_name in {"code", "git", "file", "documentation", "web_research"}:
            return self.skills.execute_skill(skill_name, action=action, **args)

        if skill_name:
            kwargs = dict(args)
            if action:
                kwargs["action"] = action
            return self.skills.execute_skill(skill_name, **kwargs)

        return SkillResult.fail(f"Cannot execute step: skill={skill_name}, action={action}")

    def _record_step_feedback(self, step: PlanStep, result: SkillResult) -> None:
        """Record step outcome into reflection, learning, memory, and developmental engines."""
        action = str(step.args.get("action", ""))
        outcome = SkillOutcome(
            skill_name=step.action,
            action=action,
            success=result.success,
            duration_ms=self._result_duration_ms(result),
            output=str(result.output or ""),
            errors=list(result.errors),
            warnings=list(result.warnings),
            metadata={
                "step_id": step.id,
                "description": step.description,
                **dict(result.metadata),
            },
        )
        self.reflection.reflect_skill(outcome)
        self.learning.record_skill_use(outcome)

        episode = EpisodicItem(
            importance=0.6 if result.success else 0.4,
            structured_input={"objective_step": step.description},
            decision={
                "skill": step.action,
                "action": action,
                "args": step.args,
            },
            outcome=Outcome.SUCCESS.value if result.success else Outcome.FAILED.value,
            notes=str(result.output or "; ".join(result.errors)),
        )
        self.memory.store_episodic(episode)
        try:
            self.memory.record_outcome(
                episode.id,
                Outcome.SUCCESS if result.success else Outcome.FAILED,
                notes=episode.notes,
            )
        except NotImplementedError:
            pass

        # Record outcome for identity formation
        self.identity.observe_action(
            action_type=step.action,
            outcome="success" if result.success else "failed",
            context={
                "skill": step.action,
                "action": action,
                "duration_ms": self._result_duration_ms(result),
                "risk_level": "low",  # Default, could be enhanced
                "retries": 0,
            },
        )

        # Record outcome for value formation
        self.values.observe_outcome(
            action_type=step.action,
            outcome="success" if result.success else "failed",
            context={
                "duration_ms": self._result_duration_ms(result),
                "retries": 0,
                "risk_level": "low",
                "complexity": "medium",
                "completeness": "high" if result.success else "low",
                "speed": "fast" if self._result_duration_ms(result) < 1000 else "slow",
            },
        )

    @staticmethod
    def _result_duration_ms(result: SkillResult) -> float:
        if result.duration_ms:
            return result.duration_ms
        for key in ("duration_ms", "elapsed"):
            value = result.metadata.get(key)
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return 0.0
        return 0.0

    def get_status(self) -> dict:
        """Comprehensive status of all ARIA systems, including developmental state."""
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
            "developmental": {
                "identity": {
                    "coherence": self.identity.state.identity_coherence,
                    "total_experiences": self.identity.state.total_experiences,
                    "stable_preferences": len(self.identity.get_stable_preferences()),
                    "summary": self.identity.get_identity_summary(),
                },
                "values": {
                    "coherence": self.values.state.value_coherence,
                    "total_signals": self.values.state.total_signals,
                    "stable_values": len(self.values.get_stable_values()),
                    "conflicts": len(self.values.state.conflicts),
                    "summary": self.values.get_value_summary(),
                },
                "memory_influence": self.memory_influence.get_influence_summary(),
            },
        }

    def shutdown(self) -> None:
        self.knowledge.close()
        self.memory.close()
        self.checkpoint.close()
        logger.info("ARIACore shut down")
