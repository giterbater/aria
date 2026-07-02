from __future__ import annotations

from dataclasses import dataclass, field


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
