from __future__ import annotations

import logging
from typing import Dict, List

from .interfaces import ToolProtocol, ToolResult

logger = logging.getLogger("aria.cto.tools")


class CTOToolRegistry:
    """Dispatch table mapping tool names to ToolProtocol instances."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolProtocol] = {}

    def register(self, tool: ToolProtocol) -> None:
        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s", tool.name)

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def dispatch(self, name: str, args: dict | None = None) -> ToolResult:
        args = args or {}
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                success=False,
                output=f"unknown tool: {name}",
                metadata={"known_tools": sorted(self._tools)},
            )
        try:
            return tool.execute(**args)
        except TypeError as exc:
            return ToolResult(
                success=False,
                output=f"tool {name!r} got bad args: {exc}",
                metadata={"args": args},
            )
        except Exception as exc:
            logger.exception("Tool %s raised", name)
            return ToolResult(
                success=False,
                output=f"tool {name!r} raised: {exc}",
                metadata={"args": args},
            )

    def known_tools(self) -> List[str]:
        return sorted(self._tools)

    def get(self, name: str) -> ToolProtocol | None:
        return self._tools.get(name)

    @classmethod
    def with_defaults(cls) -> CTOToolRegistry:
        from .repo_tools import ListFilesTool, GetStructureTool, ReadFileTool, SearchCodeTool
        from .file_editor import ApplyEditTool, CreateFileTool, DeleteFileTool
        from .terminal import RunCommandTool
        from .test_runner import RunTestsTool

        reg = cls()
        for tool_cls in [
            ListFilesTool, GetStructureTool, ReadFileTool, SearchCodeTool,
            ApplyEditTool, CreateFileTool, DeleteFileTool,
            RunCommandTool, RunTestsTool,
        ]:
            reg.register(tool_cls())
        return reg
