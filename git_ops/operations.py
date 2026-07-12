from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from tools.interfaces import ToolResult

logger = logging.getLogger("aria.cto.git")


class GitOperationsImpl:
    """Git operations via subprocess. Never raises; returns ToolResult."""

    def __init__(self, default_cwd: str | None = None) -> None:
        self._default_cwd = default_cwd

    def _run(self, cwd: str, *args: str) -> subprocess.CompletedProcess[str]:
        working_dir = cwd or self._default_cwd
        cmd = ["git"] + list(args)
        logger.debug("git %s (cwd=%s)", " ".join(args), working_dir)
        return subprocess.run(
            cmd,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def status(self, cwd: str) -> ToolResult:
        result = self._run(cwd, "status", "--porcelain")
        if result.returncode != 0:
            return ToolResult(success=False, output=f"git status failed: {result.stderr.strip()}")
        output = result.stdout.strip() or "(clean working tree)"
        return ToolResult(success=True, output=output, metadata={"raw": result.stdout})

    def diff(self, cwd: str, staged: bool = False) -> ToolResult:
        args = ["diff", "--staged"] if staged else ["diff"]
        result = self._run(cwd, *args)
        if result.returncode != 0:
            return ToolResult(success=False, output=f"git diff failed: {result.stderr.strip()}")
        output = result.stdout.strip() or "(no changes)"
        return ToolResult(success=True, output=output, metadata={"staged": staged})

    def log(self, cwd: str, n: int = 10) -> ToolResult:
        result = self._run(cwd, "log", f"-{n}", "--oneline", "--decorate")
        if result.returncode != 0:
            return ToolResult(success=False, output=f"git log failed: {result.stderr.strip()}")
        output = result.stdout.strip() or "(no commits)"
        return ToolResult(success=True, output=output)

    def add(self, cwd: str, paths: list[str]) -> ToolResult:
        if not paths:
            return ToolResult(success=False, output="no paths provided")
        result = self._run(cwd, "add", "--", *paths)
        if result.returncode != 0:
            return ToolResult(success=False, output=f"git add failed: {result.stderr.strip()}")
        return ToolResult(success=True, output=f"staged {len(paths)} file(s)", metadata={"paths": paths})

    def commit(self, cwd: str, message: str) -> ToolResult:
        if not message.strip():
            return ToolResult(success=False, output="commit message cannot be empty")
        result = self._run(cwd, "commit", "-m", message)
        if result.returncode != 0:
            return ToolResult(success=False, output=f"git commit failed: {result.stderr.strip()}")
        return ToolResult(success=True, output=result.stdout.strip(), metadata={"message": message})

    def branch_list(self, cwd: str) -> ToolResult:
        result = self._run(cwd, "branch", "-a")
        if result.returncode != 0:
            return ToolResult(success=False, output=f"git branch failed: {result.stderr.strip()}")
        return ToolResult(success=True, output=result.stdout.strip() or "(no branches)")

    def branch_create(self, cwd: str, name: str) -> ToolResult:
        result = self._run(cwd, "checkout", "-b", name)
        if result.returncode != 0:
            return ToolResult(success=False, output=f"git branch create failed: {result.stderr.strip()}")
        return ToolResult(success=True, output=f"created and switched to branch: {name}")

    def branch_delete(self, cwd: str, name: str) -> ToolResult:
        result = self._run(cwd, "branch", "-D", name)
        if result.returncode != 0:
            return ToolResult(success=False, output=f"git branch delete failed: {result.stderr.strip()}")
        return ToolResult(success=True, output=f"deleted branch: {name}")

    def checkout(self, cwd: str, target: str) -> ToolResult:
        result = self._run(cwd, "checkout", target)
        if result.returncode != 0:
            return ToolResult(success=False, output=f"git checkout failed: {result.stderr.strip()}")
        return ToolResult(success=True, output=f"checked out: {target}")

    def push(self, cwd: str, remote: str = "origin", branch: str = "HEAD") -> ToolResult:
        result = self._run(cwd, "push", remote, branch)
        if result.returncode != 0:
            return ToolResult(success=False, output=f"git push failed: {result.stderr.strip()}")
        return ToolResult(success=True, output=result.stdout.strip() or "pushed")

    def pull(self, cwd: str, remote: str = "origin", branch: str = "HEAD") -> ToolResult:
        result = self._run(cwd, "pull", remote, branch)
        if result.returncode != 0:
            return ToolResult(success=False, output=f"git pull failed: {result.stderr.strip()}")
        return ToolResult(success=True, output=result.stdout.strip() or "pulled")

    def reset_hard(self, cwd: str, target: str = "HEAD") -> ToolResult:
        result = self._run(cwd, "reset", "--hard", target)
        if result.returncode != 0:
            return ToolResult(success=False, output=f"git reset failed: {result.stderr.strip()}")
        return ToolResult(success=True, output=f"reset to {target}")

    def force_push(self, cwd: str, remote: str = "origin", branch: str = "HEAD") -> ToolResult:
        result = self._run(cwd, "push", "--force", remote, branch)
        if result.returncode != 0:
            return ToolResult(success=False, output=f"git force push failed: {result.stderr.strip()}")
        return ToolResult(success=True, output=result.stdout.strip() or "force pushed")
