from __future__ import annotations

import pytest
from tools.test_runner import RunTestsTool


class TestRunTestsTool:
    def test_run_with_default_cwd(self):
        tool = RunTestsTool(default_cwd=".")
        result = tool.execute(path="tests/test_cto_config.py", timeout=60)
        assert result.success is True
        assert "EXIT CODE" in result.output

    def test_run_specific_path(self):
        tool = RunTestsTool(default_cwd=".")
        result = tool.execute(path="tests/test_cto_config.py", timeout=30)
        assert "EXIT CODE" in result.output

    def test_run_nonexistent_cwd(self):
        tool = RunTestsTool()
        result = tool.execute(cwd="/nonexistent/dir")
        assert result.success is False
