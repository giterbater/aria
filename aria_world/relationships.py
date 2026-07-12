"""Relationship graph — trust, social bonds, reputation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Relationship:
    agent_id: str
    trust: float = 50.0
    trades_completed: int = 0
    conflicts_had: int = 0
    last_interaction_day: int = 0


class RelationshipGraph:
    def __init__(self) -> None:
        self._edges: dict[tuple[str, str], Relationship] = {}

    def _key(self, a: str, b: str) -> tuple[str, str]:
        return (a, b) if a <= b else (b, a)

    def add_agent(self, agent_id: str) -> None:
        pass

    def initialize_pair(self, a_id: str, b_id: str, trust: float = 50.0, day: int = 0) -> None:
        key = self._key(a_id, b_id)
        self._edges[key] = Relationship(agent_id=b_id if a_id <= b_id else a_id, trust=trust, last_interaction_day=day)

    def get_trust(self, a_id: str, b_id: str) -> float:
        key = self._key(a_id, b_id)
        rel = self._edges.get(key)
        return rel.trust if rel else 50.0

    def update_trust(self, a_id: str, b_id: str, delta: float, day: int = 0) -> None:
        key = self._key(a_id, b_id)
        if key not in self._edges:
            self._edges[key] = Relationship(agent_id=b_id if a_id <= b_id else a_id)
        rel = self._edges[key]
        rel.trust = max(0.0, min(100.0, rel.trust + delta))
        rel.last_interaction_day = day

    def record_trade(self, a_id: str, b_id: str, value: float, day: int = 0) -> None:
        key = self._key(a_id, b_id)
        if key not in self._edges:
            self._edges[key] = Relationship(agent_id=b_id if a_id <= b_id else a_id)
        rel = self._edges[key]
        rel.trust = max(0.0, min(100.0, rel.trust + value * 0.1))
        rel.trades_completed += 1
        rel.last_interaction_day = day

    def record_conflict(self, a_id: str, b_id: str, day: int = 0) -> None:
        key = self._key(a_id, b_id)
        if key not in self._edges:
            self._edges[key] = Relationship(agent_id=b_id if a_id <= b_id else a_id)
        rel = self._edges[key]
        rel.trust = max(0.0, rel.trust - 15.0)
        rel.conflicts_had += 1
        rel.last_interaction_day = day

    def record_socialize(self, a_id: str, b_id: str, day: int = 0) -> None:
        self.update_trust(a_id, b_id, 3.0, day)

    def get_most_trusted(self, agent_id: str, limit: int = 3) -> list[tuple[str, float]]:
        scores: list[tuple[str, float]] = []
        for (a, b), rel in self._edges.items():
            other = b if a == agent_id else (a if b == agent_id else None)
            if other:
                scores.append((other, rel.trust))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:limit]

    def get_all_trust_for(self, agent_id: str) -> dict[str, float]:
        result: dict[str, float] = {}
        for (a, b), rel in self._edges.items():
            if a == agent_id:
                result[b] = rel.trust
            elif b == agent_id:
                result[a] = rel.trust
        return result

    def average_trust(self) -> float:
        if not self._edges:
            return 50.0
        return sum(r.trust for r in self._edges.values()) / len(self._edges)

    def count(self) -> int:
        return len(self._edges)
