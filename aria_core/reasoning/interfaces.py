from __future__ import annotations

from dataclasses import dataclass, field

from ..planning.interfaces import Plan, PlanStep


@dataclass
class ConfidenceScore:
    """Confidence estimate for a reasoning decision."""
    goal: float = 0.0
    plan: float = 0.0
    skill_selection: float = 0.0
    memory_match: float = 0.0

    @property
    def overall(self) -> float:
        values = [self.goal, self.plan, self.skill_selection, self.memory_match]
        return sum(values) / len(values) if values else 0.0

    @property
    def is_confident(self) -> bool:
        return self.overall >= 0.7

    def summary(self) -> str:
        return (
            f"Goal: {self.goal:.0%} | Plan: {self.plan:.0%} | "
            f"Skill: {self.skill_selection:.0%} | Memory: {self.memory_match:.0%} | "
            f"Overall: {self.overall:.0%}"
        )


@dataclass
class ReasoningContext:
    """All context gathered before reasoning about an objective."""
    objective: str = ""
    available_skills: list[str] = field(default_factory=list)
    known_patterns: list[str] = field(default_factory=list)
    failure_modes: list[str] = field(default_factory=list)
    recent_actions: list[str] = field(default_factory=list)
    active_goals: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)


@dataclass
class ReasonedPlan:
    """A plan produced by the reasoning engine with confidence and verification."""
    objective: str = ""
    steps: list[dict] = field(default_factory=list)
    confidence: ConfidenceScore = field(default_factory=ConfidenceScore)
    reasoning: str = ""
    risks: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)
    verified: bool = False
    verification_notes: list[str] = field(default_factory=list)

    def to_plan(self) -> Plan:
        """Adapt dict-based reasoning steps into the typed planning model.

        This is a migration adapter for the current reasoning contract. New
        execution code should use the returned ``Plan`` instead of mutating
        ``steps`` directly.
        """
        typed_steps: list[PlanStep] = []
        known_ids: set[str] = set()

        for index, step in enumerate(self.steps):
            raw_id = step.get("id", index + 1)
            step_id = str(raw_id)
            known_ids.add(step_id)

            skill = str(step.get("skill") or step.get("action") or "reason")
            action = step.get("action", "")
            args = dict(step.get("args") or {})
            if action:
                args.setdefault("action", action)

            deps = [str(dep) for dep in step.get("dependencies", step.get("depends_on", []))]
            typed_steps.append(
                PlanStep(
                    id=step_id,
                    description=str(step.get("description", "")),
                    action=skill,
                    args=args,
                    depends_on=deps,
                )
            )

        for typed_step in typed_steps:
            typed_step.depends_on = [dep for dep in typed_step.depends_on if dep in known_ids]

        return Plan(
            id=f"reasoned:{abs(hash((self.objective, len(self.steps))))}",
            objective=self.objective,
            steps=typed_steps,
        )
