"""CTO-to-OpenHands bridge.

Allows the CTO agent to delegate execution tasks to OpenHands
while retaining planning and engineering decision authority.
"""
from __future__ import annotations

import json
import logging
import subprocess
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("aria.cto.openhands")

OPENHANDS_WORKSPACE = r"C:\Users\nevaan kaul\aria_project"
OPENHANDS_SCRIPT = r"C:\Users\nevaan kaul\aria_project\openhands\start.ps1"


@dataclass
class ExecutionResult:
    """Result of an OpenHands execution task."""
    success: bool
    output: str
    files_modified: list[str] = field(default_factory=list)
    error: str = ""


class OpenHandsBridge:
    """Bridge between CTO planning and OpenHands execution.

    The CTO decides WHAT to do. OpenHands does HOW.
    """

    def __init__(self, workspace: str = OPENHANDS_WORKSPACE) -> None:
        self.workspace = workspace
        self._validate_environment()

    def _validate_environment(self) -> None:
        """Check that OpenHands prerequisites are met."""
        issues = []

        if not Path(self.workspace).is_dir():
            issues.append(f"Workspace not found: {self.workspace}")

        config_path = Path.home() / ".openhands" / "config.toml"
        if not config_path.exists():
            issues.append(f"OpenHands config not found: {config_path}")

        env_path = Path(self.workspace) / "openhands" / ".env"
        if not env_path.exists():
            issues.append(f"OpenHands .env not found: {env_path}")

        if issues:
            logger.warning("OpenHands environment issues: %s", "; ".join(issues))

    def execute_task(self, task_description: str) -> ExecutionResult:
        """Execute a task via OpenHands.

        This sends the task to the OpenHands agent server API.
        The CTO retains authority over what gets executed.
        """
        # For now, delegate via the CLI/script approach
        # Full API integration would use the agent-server REST API
        logger.info("Delegating to OpenHands: %s", task_description[:100])

        try:
            # Write task to a temporary file for OpenHands to pick up
            task_file = Path(self.workspace) / ".aria" / "openhands_task.json"
            task_file.parent.mkdir(parents=True, exist_ok=True)

            task_data = {
                "task": task_description,
                "workspace": self.workspace,
                "source": "cto",
            }
            task_file.write_text(json.dumps(task_data, indent=2))

            return ExecutionResult(
                success=True,
                output=f"Task queued for OpenHands: {task_description[:200]}",
            )
        except Exception as exc:
            return ExecutionResult(
                success=False,
                output="",
                error=str(exc),
            )

    def run_tests(self) -> ExecutionResult:
        """Run the test suite via subprocess (safe operation)."""
        try:
            result = subprocess.run(
                [os.sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
                capture_output=True,
                text=True,
                cwd=self.workspace,
                timeout=120,
            )
            return ExecutionResult(
                success=result.returncode == 0,
                output=result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout,
                error=result.stderr[-500:] if result.stderr else "",
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(success=False, output="", error="Tests timed out after 120s")
        except Exception as exc:
            return ExecutionResult(success=False, output="", error=str(exc))

    def git_status(self) -> ExecutionResult:
        """Get git status (safe operation)."""
        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True,
                text=True,
                cwd=self.workspace,
            )
            return ExecutionResult(
                success=result.returncode == 0,
                output=result.stdout,
            )
        except Exception as exc:
            return ExecutionResult(success=False, output="", error=str(exc))

    def git_diff(self, file_path: str | None = None) -> ExecutionResult:
        """Get git diff (safe operation)."""
        cmd = ["git", "diff"]
        if file_path:
            cmd.append(file_path)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.workspace,
            )
            return ExecutionResult(
                success=result.returncode == 0,
                output=result.stdout[:3000],
            )
        except Exception as exc:
            return ExecutionResult(success=False, output="", error=str(exc))

    def is_available(self) -> bool:
        """Check if OpenHands is reachable."""
        config_path = Path.home() / ".openhands" / "config.toml"
        env_path = Path(self.workspace) / "openhands" / ".env"
        return config_path.exists() and env_path.exists()
