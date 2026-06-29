from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from .interfaces import ToolResult


def _find_python_with_pytest() -> str:
    """Find a Python executable that has pytest installed."""
    candidates = [sys.executable, "python", "python3"]
    for py in candidates:
        try:
            result = subprocess.run(
                [py, "-c", "import pytest; print(pytest.__version__)"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return py
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return sys.executable


class RunTestsTool:
    name = "run_tests"
    description = "Run pytest tests and return results"
    destructive = False

    def __init__(self, default_cwd: str | None = None) -> None:
        self._default_cwd = default_cwd
        self._python: str | None = None

    @property
    def python(self) -> str:
        if self._python is None:
            self._python = _find_python_with_pytest()
        return self._python

    def execute(self, path: str | None = None, cwd: str | None = None, timeout: int = 120) -> ToolResult:
        working_dir = cwd or self._default_cwd
        if working_dir and not Path(working_dir).exists():
            return ToolResult(success=False, output=f"working directory does not exist: {working_dir}")

        cmd_parts = [self.python, "-m", "pytest"]
        if path:
            cmd_parts.append(path)
        cmd_parts.extend(["-v", "--tb=short", "--no-header"])

        command = cmd_parts

        try:
            result = subprocess.run(
                command,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            output = result.stdout.strip()
            stderr = result.stderr.strip()
            success = result.returncode == 0

            parts = []
            if output:
                parts.append(output)
            if stderr and not success:
                parts.append(f"STDERR:\n{stderr}")
            parts.append(f"EXIT CODE: {result.returncode}")

            return ToolResult(
                success=success,
                output="\n\n".join(parts),
                metadata={
                    "returncode": result.returncode,
                    "output": output,
                    "stderr": stderr,
                },
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output=f"tests timed out after {timeout}s",
            )
        except Exception as exc:
            return ToolResult(success=False, output=f"run_tests error: {exc}")
