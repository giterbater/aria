from __future__ import annotations

import pytest
from tools.registry import CTOToolRegistry
from tools.interfaces import ToolResult


class MockTool:
    name = "mock_tool"
    description = "A mock tool for testing"
    destructive = False

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, output="mock result", metadata={"mock": True})


class FailingTool:
    name = "failing_tool"
    description = "A tool that fails"
    destructive = False

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=False, output="mock failure")


class TestCTOToolRegistry:
    def test_register_and_dispatch(self):
        reg = CTOToolRegistry()
        reg.register(MockTool())
        result = reg.dispatch("mock_tool", {"key": "value"})
        assert result.success is True
        assert result.output == "mock result"

    def test_dispatch_unknown(self):
        reg = CTOToolRegistry()
        result = reg.dispatch("nonexistent")
        assert result.success is False
        assert "unknown tool" in result.output

    def test_known_tools(self):
        reg = CTOToolRegistry()
        reg.register(MockTool())
        reg.register(FailingTool())
        tools = reg.known_tools()
        assert "failing_tool" in tools
        assert "mock_tool" in tools

    def test_unregister(self):
        reg = CTOToolRegistry()
        reg.register(MockTool())
        reg.unregister("mock_tool")
        result = reg.dispatch("mock_tool")
        assert result.success is False

    def test_get_tool(self):
        reg = CTOToolRegistry()
        tool = MockTool()
        reg.register(tool)
        assert reg.get("mock_tool") is tool
        assert reg.get("nonexistent") is None

    def test_dispatch_bad_args(self):
        reg = CTOToolRegistry()
        reg.register(MockTool())
        # MockTool.execute takes **kwargs, so this won't fail on bad args
        # but a tool with specific params would
        result = reg.dispatch("mock_tool")
        assert result.success is True
