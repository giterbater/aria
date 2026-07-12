from __future__ import annotations

from pathlib import Path

from .interfaces import ToolResult


class ApplyEditTool:
    name = "apply_edit"
    description = "Apply a search-and-replace edit to a file"
    destructive = False

    def execute(self, path: str, old_string: str, new_string: str) -> ToolResult:
        try:
            p = Path(path).resolve()
            if not p.exists():
                return ToolResult(success=False, output=f"file not found: {path}")

            content = p.read_text(encoding="utf-8")
            count = content.count(old_string)

            if count == 0:
                return ToolResult(success=False, output=f"old_string not found in {path}")
            if count > 1:
                return ToolResult(
                    success=False,
                    output=f"found {count} matches for old_string in {path}. Provide more surrounding context.",
                )

            new_content = content.replace(old_string, new_string, 1)
            p.write_text(new_content, encoding="utf-8")

            return ToolResult(
                success=True,
                output=f"edited {path}",
                metadata={"path": str(p)},
            )
        except Exception as exc:
            return ToolResult(success=False, output=f"apply_edit error: {exc}")


class CreateFileTool:
    name = "create_file"
    description = "Create a new file with given content"
    destructive = False

    def execute(self, path: str, content: str = "") -> ToolResult:
        try:
            p = Path(path).resolve()
            if p.exists():
                return ToolResult(success=False, output=f"file already exists: {path}")

            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")

            return ToolResult(
                success=True,
                output=f"created {path}",
                metadata={"path": str(p)},
            )
        except Exception as exc:
            return ToolResult(success=False, output=f"create_file error: {exc}")


class DeleteFileTool:
    name = "delete_file"
    description = "Delete a file"
    destructive = True

    def execute(self, path: str) -> ToolResult:
        try:
            p = Path(path).resolve()
            if not p.exists():
                return ToolResult(success=False, output=f"file not found: {path}")
            if not p.is_file():
                return ToolResult(success=False, output=f"not a file: {path}")

            p.unlink()
            return ToolResult(
                success=True,
                output=f"deleted {path}",
                metadata={"path": str(p)},
            )
        except Exception as exc:
            return ToolResult(success=False, output=f"delete_file error: {exc}")
