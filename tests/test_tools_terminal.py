from __future__ import annotations

import pytest
from tools.terminal import RunCommandTool


class TestRunCommandTool:
    def test_run_echo(self):
        tool = RunCommandTool()
        result = tool.execute(command="echo hello")
        assert result.success is True
        assert "hello" in result.output
        assert result.metadata["returncode"] == 0

    def test_run_failing_command(self):
        tool = RunCommandTool()
        result = tool.execute(command="python -c \"import sys; sys.exit(1)\"")
        assert result.success is False
        assert result.metadata["returncode"] == 1

    def test_run_with_cwd(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("content")
        tool = RunCommandTool()
        result = tool.execute(command="type test.txt" if __import__("sys").platform == "win32" else "cat test.txt", cwd=str(tmp_path))
        assert result.success is True
        assert "content" in result.output

    def test_run_nonexistent_cwd(self):
        tool = RunCommandTool()
        result = tool.execute(command="echo hi", cwd="/nonexistent/dir")
        assert result.success is False

    def test_run_timeout(self):
        tool = RunCommandTool()
        result = tool.execute(command="python -c \"import time; time.sleep(10)\"", timeout=1)
        assert result.success is False
        assert "timed out" in result.output

    def test_metadata_fields(self):
        tool = RunCommandTool()
        result = tool.execute(command="echo test")
        assert "returncode" in result.metadata
        assert "stdout" in result.metadata
        assert "elapsed" in result.metadata
