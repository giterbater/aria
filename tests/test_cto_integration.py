from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock
from cto.cli import _parse_response, _validate_environment
from cto.config import CTOConfig


class TestParseResponse:
    def test_valid_json(self):
        raw = '{"action": "read_file", "args": {"path": "test.py"}}'
        result = _parse_response(raw)
        assert result["action"] == "read_file"

    def test_json_in_codeblock(self):
        raw = '```json\n{"action": "read_file", "args": {"path": "test.py"}}\n```'
        result = _parse_response(raw)
        assert result["action"] == "read_file"

    def test_invalid_json_fallback(self):
        raw = "This is just plain text"
        result = _parse_response(raw)
        assert result["action"] is None
        assert result["response"] == "This is just plain text"


class TestEnvironmentValidation:
    def test_missing_repo(self):
        config = CTOConfig(repo_path="/nonexistent/path")
        issues = _validate_environment(config)
        assert any("not found" in i.lower() or "not a git" in i.lower() for i in issues)

    def test_valid_repo(self, tmp_path):
        import subprocess
        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        config = CTOConfig(repo_path=str(tmp_path))
        issues = _validate_environment(config)
        git_issues = [i for i in issues if "git" in i.lower() and "not" in i.lower()]
        assert len(git_issues) == 0


class TestToolResultMetadata:
    def test_run_command_metadata(self):
        from tools.terminal import RunCommandTool
        tool = RunCommandTool()
        result = tool.execute(command="echo test")
        assert "returncode" in result.metadata
        assert "stdout" in result.metadata
        assert "elapsed" in result.metadata

    def test_run_tests_missing_pytest(self):
        from tools.test_runner import RunTestsTool
        tool = RunTestsTool()
        if not tool.has_pytest:
            result = tool.execute()
            assert result.success is False
            assert "pytest not available" in result.output
