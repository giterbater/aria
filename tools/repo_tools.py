from __future__ import annotations

import os
from pathlib import Path
from typing import List

from .interfaces import ToolResult


class ListFilesTool:
    name = "list_files"
    description = "List files and directories at a given path"
    destructive = False

    def execute(self, path: str = ".", recursive: bool = False, pattern: str | None = None) -> ToolResult:
        try:
            base = Path(path).resolve()
            if not base.exists():
                return ToolResult(success=False, output=f"path does not exist: {path}")
            if not base.is_dir():
                return ToolResult(success=False, output=f"path is not a directory: {path}")

            entries: List[str] = []
            if recursive:
                for root, dirs, files in os.walk(base):
                    rel_root = Path(root).relative_to(base)
                    for d in sorted(dirs):
                        entries.append(f"{rel_root / d}/")
                    for f in sorted(files):
                        fp = rel_root / f
                        if pattern and not Path(f).match(pattern):
                            continue
                        entries.append(str(fp))
            else:
                for item in sorted(base.iterdir()):
                    rel = item.relative_to(base)
                    if item.is_dir():
                        entries.append(f"{rel}/")
                    else:
                        if pattern and not Path(item.name).match(pattern):
                            continue
                        entries.append(str(rel))

            return ToolResult(
                success=True,
                output="\n".join(entries) if entries else "(empty)",
                metadata={"count": len(entries), "path": str(base)},
            )
        except Exception as exc:
            return ToolResult(success=False, output=f"list_files error: {exc}")


class GetStructureTool:
    name = "get_structure"
    description = "Get a tree-like structure of the project"
    destructive = False

    def execute(self, path: str = ".", max_depth: int = 3, ignore: list[str] | None = None) -> ToolResult:
        ignore = ignore or ["__pycache__", ".git", "node_modules", ".venv", "*.pyc"]
        try:
            base = Path(path).resolve()
            if not base.exists():
                return ToolResult(success=False, output=f"path does not exist: {path}")

            lines: List[str] = []
            self._walk(base, base, lines, 0, max_depth, ignore)
            return ToolResult(
                success=True,
                output="\n".join(lines),
                metadata={"path": str(base)},
            )
        except Exception as exc:
            return ToolResult(success=False, output=f"get_structure error: {exc}")

    def _walk(self, current: Path, base: Path, lines: List[str], depth: int, max_depth: int, ignore: list[str]) -> None:
        if depth >= max_depth:
            return
        indent = "  " * depth
        try:
            entries = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name))
        except PermissionError:
            return
        for entry in entries:
            if any(entry.name == ign or entry.match(ign) for ign in ignore):
                continue
            rel = entry.relative_to(base).as_posix()
            if entry.is_dir():
                lines.append(f"{indent}{rel}/")
                self._walk(entry, base, lines, depth + 1, max_depth, ignore)
            else:
                lines.append(f"{indent}{rel}")


class ReadFileTool:
    name = "read_file"
    description = "Read the contents of a file"
    destructive = False

    def execute(self, path: str, offset: int = 0, limit: int = 2000) -> ToolResult:
        try:
            p = Path(path).resolve()
            if not p.exists():
                return ToolResult(success=False, output=f"file not found: {path}")
            if not p.is_file():
                return ToolResult(success=False, output=f"not a file: {path}")

            text = p.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            total = len(lines)
            sliced = lines[offset:offset + limit]
            content = "\n".join(f"{i + offset + 1}: {line}" for i, line in enumerate(sliced))

            return ToolResult(
                success=True,
                output=content if content else "(empty file)",
                metadata={"total_lines": total, "offset": offset, "limit": limit, "path": str(p)},
            )
        except Exception as exc:
            return ToolResult(success=False, output=f"read_file error: {exc}")


class SearchCodeTool:
    name = "search_code"
    description = "Search file contents for a regex pattern"
    destructive = False

    def execute(self, pattern: str, path: str = ".", include: str | None = None, max_results: int = 50) -> ToolResult:
        import re
        try:
            base = Path(path).resolve()
            if not base.exists():
                return ToolResult(success=False, output=f"path does not exist: {path}")

            regex = re.compile(pattern, re.IGNORECASE)
            results: List[str] = []

            search_files = []
            if base.is_file():
                search_files = [base]
            else:
                for root, dirs, files in os.walk(base):
                    dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "node_modules", ".venv")]
                    for f in files:
                        if include and not f.endswith(include.lstrip("*")):
                            continue
                        search_files.append(Path(root) / f)

            for fp in search_files:
                try:
                    text = fp.read_text(encoding="utf-8", errors="replace")
                    for i, line in enumerate(text.splitlines(), 1):
                        if regex.search(line):
                            rel = fp.relative_to(base) if base.is_dir() else fp.name
                            results.append(f"{rel}:{i}: {line.strip()}")
                            if len(results) >= max_results:
                                break
                except (UnicodeDecodeError, PermissionError):
                    continue
                if len(results) >= max_results:
                    break

            return ToolResult(
                success=True,
                output="\n".join(results) if results else "(no matches)",
                metadata={"matches": len(results), "pattern": pattern},
            )
        except re.error as exc:
            return ToolResult(success=False, output=f"invalid regex: {exc}")
        except Exception as exc:
            return ToolResult(success=False, output=f"search_code error: {exc}")
