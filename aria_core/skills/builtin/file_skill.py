from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from ..interfaces import Skill, SkillResult, SkillMeta


class FileSkill:
    """File operations: read, write, edit, create, move, delete, list."""

    def __init__(self, base_path: str | None = None) -> None:
        self._base = Path(base_path).resolve() if base_path else Path.cwd()

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="file",
            description="Read, write, edit, create, move, and delete files",
            category="file",
            tags=["read", "write", "edit", "create", "move", "delete", "file", "filesystem"],
            timeout_seconds=10.0,
        )

    def validate(self, action: str = "read", path: str = "", **kwargs) -> bool:
        if not path:
            return False
        target = self._resolve(path)
        if action == "read":
            return target.exists() and target.is_file()
        if action in ("write", "create"):
            return True
        if action == "edit":
            return target.exists() and target.is_file()
        if action == "move":
            return target.exists()
        if action == "delete":
            return target.exists() and target.is_file()
        if action == "list":
            return target.exists() and target.is_dir()
        return False

    def execute(self, action: str = "read", path: str = "", content: str = "", **kwargs) -> SkillResult:
        t0 = time.monotonic()
        try:
            if action == "read":
                result = self._read(path)
            elif action == "write":
                result = self._write(path, content)
            elif action == "create":
                result = self._create(path, content)
            elif action == "edit":
                result = self._edit(path, kwargs.get("old_string", ""), kwargs.get("new_string", ""))
            elif action == "move":
                result = self._move(path, kwargs.get("destination", ""))
            elif action == "delete":
                result = self._delete(path)
            elif action == "list":
                result = self._list(path, kwargs.get("recursive", False))
            else:
                result = SkillResult.fail(f"Unknown action: {action}")

            elapsed = (time.monotonic() - t0) * 1000
            result.metadata["duration_ms"] = round(elapsed, 1)
            return result
        except Exception as exc:
            elapsed = (time.monotonic() - t0) * 1000
            return SkillResult.fail(f"File skill error: {exc}", duration_ms=elapsed)

    def rollback(self, context: dict) -> SkillResult:
        backup = context.get("backup_path")
        target = context.get("target_path")
        if backup and target and Path(backup).exists():
            shutil.copy2(backup, target)
            return SkillResult.ok(output=f"Restored {target} from backup")
        return SkillResult.fail("No backup available for rollback")

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if p.is_absolute():
            return p.resolve()
        return (self._base / p).resolve()

    def _read(self, path: str) -> SkillResult:
        p = self._resolve(path)
        if not p.exists():
            return SkillResult.fail(f"File not found: {path}")
        if not p.is_file():
            return SkillResult.fail(f"Not a file: {path}")
        text = p.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        return SkillResult.ok(
            output="\n".join(f"{i+1}: {l}" for i, l in enumerate(lines)),
            path=str(p), total_lines=len(lines),
        )

    def _write(self, path: str, content: str) -> SkillResult:
        p = self._resolve(path)
        backup = str(p) + ".bak" if p.exists() else None
        if backup:
            shutil.copy2(p, backup)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return SkillResult.ok(
            output=f"Wrote {len(content)} bytes to {path}",
            path=str(p), bytes_written=len(content), backup=backup,
        )

    def _create(self, path: str, content: str) -> SkillResult:
        p = self._resolve(path)
        if p.exists():
            return SkillResult.fail(f"File already exists: {path}")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return SkillResult.ok(output=f"Created {path}", path=str(p))

    def _edit(self, path: str, old: str, new: str) -> SkillResult:
        if not old:
            return SkillResult.fail("old_string is required")
        p = self._resolve(path)
        if not p.exists():
            return SkillResult.fail(f"File not found: {path}")
        text = p.read_text(encoding="utf-8")
        count = text.count(old)
        if count == 0:
            return SkillResult.fail("old_string not found in file")
        if count > 1:
            return SkillResult.fail(f"Found {count} matches — provide more context")
        backup = str(p) + ".bak"
        shutil.copy2(p, backup)
        new_text = text.replace(old, new, 1)
        p.write_text(new_text, encoding="utf-8")
        return SkillResult.ok(
            output=f"Edited {path}",
            path=str(p), backup=backup,
        )

    def _move(self, path: str, destination: str) -> SkillResult:
        if not destination:
            return SkillResult.fail("destination is required")
        src = self._resolve(path)
        dst = self._resolve(destination)
        if dst.exists():
            return SkillResult.fail(f"Destination exists: {destination}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return SkillResult.ok(output=f"Moved {path} to {destination}")

    def _delete(self, path: str) -> SkillResult:
        p = self._resolve(path)
        if not p.exists():
            return SkillResult.fail(f"File not found: {path}")
        backup = str(p) + ".bak"
        shutil.copy2(p, backup)
        p.unlink()
        return SkillResult.ok(output=f"Deleted {path}", backup=backup)

    def _list(self, path: str, recursive: bool) -> SkillResult:
        p = self._resolve(path)
        entries = []
        if recursive:
            for root, dirs, files in os.walk(p):
                rel = Path(root).relative_to(p)
                for f in sorted(files):
                    entries.append(str(rel / f))
        else:
            for item in sorted(p.iterdir()):
                entries.append(str(item.relative_to(p)))
        return SkillResult.ok(output="\n".join(entries), count=len(entries))
