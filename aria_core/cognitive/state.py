from __future__ import annotations

import datetime
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict


@dataclass
class CognitiveState:
    """Dynamic internal state variables that influence reasoning.

    Each value is 0.0-1.0. Updated continuously based on outcomes.
    These are computational control signals, not personality traits.
    """
    confidence: float = 0.7       # certainty in current reasoning
    curiosity: float = 0.5        # desire to acquire missing knowledge
    frustration: float = 0.0      # repeated unsuccessful attempts
    caution: float = 0.3          # perceived execution risk
    persistence: float = 0.7      # willingness to continue difficult tasks
    novelty: float = 0.5          # unfamiliarity with current context

    # Metadata
    updated_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    cycle_count: int = 0
    total_successes: int = 0
    total_failures: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0

    def to_dict(self) -> dict:
        return {
            "confidence": self.confidence,
            "curiosity": self.curiosity,
            "frustration": self.frustration,
            "caution": self.caution,
            "persistence": self.persistence,
            "novelty": self.novelty,
            "cycle_count": self.cycle_count,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
        }

    def summary(self) -> str:
        lines = [
            f"Confidence: {self.confidence:.0%}",
            f"Curiosity: {self.curiosity:.0%}",
            f"Frustration: {self.frustration:.0%}",
            f"Caution: {self.caution:.0%}",
            f"Persistence: {self.persistence:.0%}",
            f"Novelty: {self.novelty:.0%}",
            f"Cycles: {self.cycle_count} ({self.total_successes} ok, {self.total_failures} fail)",
        ]
        return "\n".join(lines)


class InternalState:
    """Persistent internal state manager.

    Maintains cognitive state across sessions via SQLite.
    Updates state based on outcomes using dampened feedback loops.
    """

    def __init__(self, db_path: str | Path = ":memory:"):
        self._db_path = str(db_path)
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.initialize()
        self._state = self._load_state()

    def initialize(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS cognitive_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    @property
    def state(self) -> CognitiveState:
        return self._state

    def update_from_outcome(
        self,
        success: bool,
        context: dict | None = None,
    ) -> CognitiveState:
        """Update internal state based on task outcome.

        Uses dampened feedback loops:
        - Success: increases confidence, decreases frustration
        - Failure: increases frustration and curiosity, decreases confidence
        - Repeated failure: increases caution, decreases persistence
        - Novel context: increases curiosity
        """
        context = context or {}
        s = self._state
        damping = 0.15  # prevent oscillation

        s.cycle_count += 1
        s.updated_at = datetime.datetime.now()

        if success:
            s.total_successes += 1
            s.consecutive_successes += 1
            s.consecutive_failures = 0

            s.confidence = min(1.0, s.confidence + damping * 0.8)
            s.frustration = max(0.0, s.frustration - damping * 1.2)
            s.persistence = min(1.0, s.persistence + damping * 0.2)
            s.caution = max(0.0, s.caution - damping * 0.3)
        else:
            s.total_failures += 1
            s.consecutive_failures += 1
            s.consecutive_successes = 0

            s.confidence = max(0.0, s.confidence - damping * 0.6)
            s.frustration = min(1.0, s.frustration + damping * 0.8)
            s.curiosity = min(1.0, s.curiosity + damping * 0.5)

            if s.consecutive_failures >= 3:
                s.caution = min(1.0, s.caution + damping * 1.0)
                s.persistence = max(0.0, s.persistence - damping * 0.5)

        is_novel = context.get("is_novel", False)
        if is_novel:
            s.novelty = min(1.0, s.novelty + damping * 0.6)
            s.curiosity = min(1.0, s.curiosity + damping * 0.4)

        unknown_count = context.get("unknown_concepts", 0)
        if unknown_count > 0:
            s.curiosity = min(1.0, s.curiosity + damping * 0.3 * unknown_count)

        self._save_state()
        return s

    def update_from_reflection(
        self,
        reflection_type: str,
        lessons_count: int,
    ) -> CognitiveState:
        """Update state based on reflection results."""
        s = self._state
        damping = 0.1

        if reflection_type == "success":
            s.confidence = min(1.0, s.confidence + damping * 0.3)
        elif reflection_type == "failure":
            s.frustration = min(1.0, s.frustration + damping * 0.2)
            s.caution = min(1.0, s.caution + damping * 0.1)
        elif reflection_type == "improvement":
            s.curiosity = min(1.0, s.curiosity + damping * 0.2)
            s.confidence = min(1.0, s.confidence + damping * 0.1)

        if lessons_count > 0:
            s.curiosity = max(0.0, s.curiosity - damping * 0.1 * lessons_count)

        self._save_state()
        return s

    def reset_after_success_streak(self, threshold: int = 5) -> None:
        """Reset frustration after a streak of successes."""
        if self._state.consecutive_successes >= threshold:
            self._state.frustration = max(0.0, self._state.frustration - 0.3)
            self._state.caution = max(0.0, self._state.caution - 0.1)
            self._save_state()

    def get_state(self) -> CognitiveState:
        return self._state

    def _save_state(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO cognitive_state (id, state_json, updated_at)
                VALUES (1, ?, ?)
                """,
                (json.dumps(self._state.to_dict()), self._state.updated_at.isoformat()),
            )

    def _load_state(self) -> CognitiveState:
        row = self._conn.execute(
            "SELECT * FROM cognitive_state WHERE id=1"
        ).fetchone()
        if row is None:
            return CognitiveState()
        data = json.loads(row["state_json"])
        return CognitiveState(
            confidence=data.get("confidence", 0.7),
            curiosity=data.get("curiosity", 0.5),
            frustration=data.get("frustration", 0.0),
            caution=data.get("caution", 0.3),
            persistence=data.get("persistence", 0.7),
            novelty=data.get("novelty", 0.5),
            cycle_count=data.get("cycle_count", 0),
            total_successes=data.get("total_successes", 0),
            total_failures=data.get("total_failures", 0),
            consecutive_failures=data.get("consecutive_failures", 0),
            consecutive_successes=data.get("consecutive_successes", 0),
        )

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.ProgrammingError:
            pass
