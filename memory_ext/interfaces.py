from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ProjectMemoryProtocol(Protocol):
    """Persistent project-level memory for the CTO agent.

    Stores decisions, roadmap items, specialist profiles, and codebase facts.
    Separate from the existing MemorySystemProtocol which handles cognitive
    memory (working/episodic/semantic).
    """

    def initialize(self) -> None:
        """Create tables if missing. Idempotent."""

    def close(self) -> None:
        """Close the underlying connection."""

    def store_decision(self, decision: dict) -> None:
        """Record a CTO cycle decision."""

    def get_recent_decisions(self, limit: int = 20) -> list[dict]:
        """Return the most recent decisions, newest first."""

    def store_roadmap_item(self, item: dict) -> None:
        """Add or update a roadmap item."""

    def get_roadmap(self) -> list[dict]:
        """Return all roadmap items ordered by priority."""

    def update_roadmap_status(self, item_id: str, status: str) -> None:
        """Update the status of a roadmap item."""

    def store_specialist_profile(self, name: str, strengths: list[str]) -> None:
        """Store or update a specialist's profile."""

    def get_specialist_profiles(self) -> dict[str, list[str]]:
        """Return all specialist profiles."""

    def record_specialist_outcome(self, name: str, success: bool) -> None:
        """Record a success/failure for a specialist."""

    def store_codebase_fact(self, key: str, value: str) -> None:
        """Store a discovered codebase fact."""

    def get_codebase_facts(self, query: str | None = None) -> list[tuple[str, str]]:
        """Return codebase facts, optionally filtered by query."""
