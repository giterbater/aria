from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from .interfaces import ToolResult


def _find_python_with_pytest() -> str | None:
    """Find a Python executable that has pytest installed. Returns None if not found."""
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
    return None


class RunTestsTool:
    name = "run_tests"
    description = "Run pytest tests and return results"
    destructive = False

    def __init__(self, default_cwd: str | None = None) -> None:
        self._default_cwd = default_cwd
        self._python: str | None = None
        self._checked = False

    @property
    def python(self) -> str:
        if not self._checked:
            self._python = _find_python_with_pytest()
            self._checked = True
        if self._python is None:
            return sys.executable
        return self._python

    @property
    def has_pytest(self) -> bool:
        if not self._checked:
            self._python = _find_python_with_pytest()
            self._checked = True
        return self._python is not None

    def execute(self, path: str | None = None, cwd: str | None = None, timeout: int = 120) -> ToolResult:
        if not self.has_pytest:
            return ToolResult(
                success=False,
                output=(
                    "pytest not available. Install it with: pip install pytest\n"
                    f"Searched: {', '.join([sys.executable, 'python', 'python3'])}"
                ),
                metadata={"error": "pytest_not_found"},
            )

        working_dir = cwd or self._default_cwd
        if working_dir and not Path(working_dir).exists():
            return ToolResult(
                success=False,
                output=f"working directory does not exist: {working_dir}",
                metadata={"error": "directory_not_found"},
            )

        cmd_parts = [self.python, "-m", "pytest"]
        if path:
            cmd_parts.append(path)
        cmd_parts.extend(["-v", "--tb=short", "--no-header"])

        t0 = time.monotonic()
        try:
            result = subprocess.run(
                cmd_parts,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            elapsed = time.monotonic() - t0

            output = result.stdout.strip()
            stderr = result.stderr.strip()
            success = result.returncode == 0

            parts = []
            if output:
                parts.append(output)
            if stderr and not success:
                parts.append(f"STDERR:\n{stderr}")
            parts.append(f"EXIT CODE: {result.returncode}")
            parts.append(f"TIME: {elapsed:.1f}s")

            return ToolResult(
                success=success,
                output="\n\n".join(parts),
                metadata={
                    "returncode": result.returncode,
                    "stdout": output,
                    "stderr": stderr,
                    "elapsed": round(elapsed, 2),
                    "python": self.python,
                },
            )
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - t0
            return ToolResult(
                success=False,
                output=f"tests timed out after {timeout}s",
                metadata={"error": "timeout", "elapsed": round(elapsed, 2)},
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                output=f"run_tests error: {exc}",
                metadata={"error": str(exc)},
            )
