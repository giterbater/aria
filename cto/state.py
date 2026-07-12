from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class CycleState:
    """Tracks the state of a single autonomous CTO cycle."""
    cycle_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    started_at: datetime = field(default_factory=datetime.now)
    phase: str = "inspect"
    actions_taken: list[dict] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    tests_passed: bool | None = None
    commit_sha: str | None = None
    error: str | None = None
    specialist_delegated: str | None = None
    review_approved: bool | None = None

    def record_action(self, action: dict) -> CycleState:
        from dataclasses import replace
        return replace(self, actions_taken=self.actions_taken + [action])

    def set_files_modified(self, files: list[str]) -> CycleState:
        from dataclasses import replace
        return replace(self, files_modified=files)

    def set_phase(self, phase: str) -> CycleState:
        from dataclasses import replace
        return replace(self, phase=phase)

    def set_error(self, error: str) -> CycleState:
        from dataclasses import replace
        return replace(self, error=error)

    def set_commit(self, sha: str) -> CycleState:
        from dataclasses import replace
        return replace(self, commit_sha=sha)

    def set_tests_result(self, passed: bool) -> CycleState:
        from dataclasses import replace
        return replace(self, tests_passed=passed)

    def set_review(self, approved: bool) -> CycleState:
        from dataclasses import replace
        return replace(self, review_approved=approved)

    def to_dict(self) -> dict:
        return {
            "cycle_id": self.cycle_id,
            "started_at": self.started_at.isoformat(),
            "phase": self.phase,
            "actions_taken": self.actions_taken,
            "files_modified": self.files_modified,
            "tests_passed": self.tests_passed,
            "commit_sha": self.commit_sha,
            "error": self.error,
            "specialist_delegated": self.specialist_delegated,
            "review_approved": self.review_approved,
        }
