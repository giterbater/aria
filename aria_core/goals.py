# aria_core/goals.py
"""
Simple goal representation and manager.
Goals are lightweight objects that ARIA Core can consult when deciding
what to do.  The manager keeps a list of active goals and can return
those that are relevant to a given cue (e.g., the current structured
input).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class Goal:
    """A goal that ARIA's internal goal model. """
    id: str = field(default_factory=lambda: str(__import__('uuid').uuid4()))
    description: str = ""          # human‑readable description
    priority: float = 1.0          # higher = more important
    deadline: Optional[datetime.datetime] = None  # optional time bound
    # Any extra metadata the caller wants to store (e.g., required resources)
    metadata: dict = field(default_factory=dict)


class GoalManager:
    """
    Holds the set of active goals and provides relevance lookup.
    In a full system you would persist goals, support addition/removal,
    and have more sophisticated matching (e.g., semantic similarity).
    """

    def __init__(self, goals: Optional[List[Goal]] = None):
        self._goals: List[Goal] = list(goals or [])

    # -----------------------------------------------------------------
    # Goal lifecycle (simple add/remove)
    # -----------------------------------------------------------------
    def add_goal(self, goal: Goal) -> None:
        self._goals.append(goal)

    def remove_goal(self, goal_id: str) -> None:
        self._goals = [g for g in self._goals if g.id != goal_id]

    def list_goals(self) -> List[Goal]:
        return list(self._goals)

    # -----------------------------------------------------------------
    # Relevance – very light‑weight keyword match.
    # Replace with a proper embedding‑based search in a production swap.
    # ------------------------------------------------------------------
    def relevant_goals(self, cue: str, *, limit: int = 5) -> List[Goal]:
        """
        Return goals whose description shares any token with *cue*.
        Ordered by priority (descending).
        """
        cue_tokens = set(cue.lower().split())
        scored: List[Goal] = []
        for g in self._goals:
            desc_tokens = set(g.description.lower().split())
            if cue_tokens & desc_tokens:          # any overlap
                scored.append(g)
        scored.sort(key=lambda g: g.priority, reverse=True)
        return scored[:limit]