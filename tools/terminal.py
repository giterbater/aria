from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

from .interfaces import ToolResult

logger = logging.getLogger("aria.cto.tools.terminal")


class RunCommandTool:
    name = "run_command"
    description = "Execute a shell command and return output"
    destructive = False

    def __init__(self, default_cwd: str | None = None) -> None:
        self._default_cwd = default_cwd

    def execute(self, command: str, cwd: str | None = None, timeout: int = 60) -> ToolResult:
        working_dir = cwd or self._default_cwd
        if working_dir and not Path(working_dir).exists():
            return ToolResult(success=False, output=f"working directory does not exist: {working_dir}")

        logger.info("Running command: %s (cwd=%s)", command, working_dir)

        start = time.monotonic()
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            elapsed = time.monotonic() - start

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            success = result.returncode == 0

            parts = []
            if stdout:
                parts.append(f"STDOUT:\n{stdout}")
            if stderr:
                parts.append(f"STDERR:\n{stderr}")
            parts.append(f"EXIT CODE: {result.returncode}")
            parts.append(f"TIME: {elapsed:.1f}s")

            return ToolResult(
                success=success,
                output="\n\n".join(parts),
                metadata={
                    "returncode": result.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                    "elapsed": round(elapsed, 2),
                },
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output=f"command timed out after {timeout}s: {command}",
            )
        except Exception as exc:
            return ToolResult(success=False, output=f"run_command error: {exc}")
