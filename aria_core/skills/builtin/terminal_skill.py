from __future__ import annotations

import subprocess
import time

from ..interfaces import Skill, SkillResult, SkillMeta


class TerminalSkill:
    """Execute shell commands with structured output."""

    def __init__(self, default_cwd: str | None = None) -> None:
        self._default_cwd = default_cwd

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="terminal",
            description="Execute shell commands",
            category="system",
            tags=["command", "shell", "execute", "terminal", "process"],
            timeout_seconds=30.0,
        )

    def validate(self, command: str = "", **kwargs) -> bool:
        return bool(command and command.strip())

    def execute(self, command: str = "", cwd: str | None = None, timeout: int = 30, **kwargs) -> SkillResult:
        working_dir = cwd or self._default_cwd
        t0 = time.monotonic()
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            elapsed = (time.monotonic() - t0) * 1000

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            success = result.returncode == 0

            parts = []
            if stdout:
                parts.append(stdout)
            if stderr:
                parts.append(f"STDERR: {stderr}")

            output = "\n".join(parts) if parts else "(no output)"

            return SkillResult(
                success=success,
                output=output,
                duration_ms=round(elapsed, 1),
                warnings=[f"stderr: {stderr}"] if stderr and success else [],
                errors=[f"stderr: {stderr}"] if stderr and not success else [],
                metadata={
                    "returncode": result.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                    "elapsed": round(elapsed, 1),
                    "command": command,
                },
            )
        except subprocess.TimeoutExpired:
            elapsed = (time.monotonic() - t0) * 1000
            return SkillResult.fail(
                f"Command timed out after {timeout}s",
                command=command, elapsed=round(elapsed, 1),
            )
        except Exception as exc:
            elapsed = (time.monotonic() - t0) * 1000
            return SkillResult.fail(f"Command error: {exc}", command=command)

    def rollback(self, context: dict) -> SkillResult:
        return SkillResult.fail("Terminal commands cannot be rolled back")
