from __future__ import annotations

import subprocess
import time

from ..interfaces import Skill, SkillResult, SkillMeta


class GitSkill:
    """Git operations: status, diff, log, branch, commit, add."""

    def __init__(self, default_cwd: str | None = None) -> None:
        self._default_cwd = default_cwd

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="git",
            description="Git version control operations",
            category="vcs",
            tags=["git", "version", "commit", "branch", "diff", "status"],
            timeout_seconds=15.0,
        )

    def validate(self, action: str = "status", **kwargs) -> bool:
        return action in ("status", "diff", "log", "add", "commit", "branch", "branch_list")

    def execute(self, action: str = "status", cwd: str | None = None, **kwargs) -> SkillResult:
        working_dir = cwd or self._default_cwd
        t0 = time.monotonic()
        try:
            if action == "status":
                result = self._run(working_dir, "status", "--porcelain")
            elif action == "diff":
                staged = kwargs.get("staged", False)
                args = ["diff", "--staged"] if staged else ["diff"]
                result = self._run(working_dir, *args)
            elif action == "log":
                n = kwargs.get("n", 10)
                result = self._run(working_dir, "log", f"-{n}", "--oneline", "--decorate")
            elif action == "add":
                paths = kwargs.get("paths", ["."])
                result = self._run(working_dir, "add", "--", *paths)
            elif action == "commit":
                message = kwargs.get("message", "")
                if not message:
                    return SkillResult.fail("commit message is required")
                result = self._run(working_dir, "commit", "-m", message)
            elif action == "branch":
                name = kwargs.get("name", "")
                if not name:
                    result = self._run(working_dir, "branch", "-a")
                else:
                    result = self._run(working_dir, "checkout", "-b", name)
            elif action == "branch_list":
                result = self._run(working_dir, "branch", "-a")
            else:
                return SkillResult.fail(f"Unknown git action: {action}")

            elapsed = (time.monotonic() - t0) * 1000

            if result.returncode != 0:
                return SkillResult.fail(
                    f"git {action} failed: {result.stderr.strip()}",
                    duration_ms=round(elapsed, 1),
                    returncode=result.returncode,
                    command=f"git {action}",
                )

            output = result.stdout.strip() or "(no output)"
            return SkillResult.ok(
                output=output,
                duration_ms=round(elapsed, 1),
                returncode=0,
                action=action,
                command=f"git {action}",
            )
        except Exception as exc:
            elapsed = (time.monotonic() - t0) * 1000
            return SkillResult.fail(f"git error: {exc}", duration_ms=round(elapsed, 1))

    def rollback(self, context: dict) -> SkillResult:
        return SkillResult.fail("Git rollback requires explicit git reset — not auto-rolled-back")

    def _run(self, cwd: str | None, *args: str) -> subprocess.CompletedProcess[str]:
        cmd = ["git"] + list(args)
        return subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=15,
        )
