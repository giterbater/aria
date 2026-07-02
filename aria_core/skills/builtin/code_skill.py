from __future__ import annotations

import ast
import time
from pathlib import Path

from ..interfaces import Skill, SkillResult, SkillMeta


class CodeSkill:
    """Code analysis: repository scan, complexity, structure, patterns."""

    def __init__(self, base_path: str | None = None) -> None:
        self._base = Path(base_path).resolve() if base_path else Path.cwd()

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="code",
            description="Code analysis, repository scanning, static analysis",
            category="code",
            tags=["code", "analysis", "scan", "structure", "complexity", "refactor"],
            timeout_seconds=30.0,
        )

    def validate(self, action: str = "scan", **kwargs) -> bool:
        return action in ("scan", "complexity", "structure", "find_patterns")

    def execute(self, action: str = "scan", **kwargs) -> SkillResult:
        t0 = time.monotonic()
        try:
            if action == "scan":
                result = self._scan(kwargs.get("path", "."))
            elif action == "complexity":
                result = self._complexity(kwargs.get("path", "."))
            elif action == "structure":
                result = self._structure(kwargs.get("path", "."))
            elif action == "find_patterns":
                result = self._find_patterns(kwargs.get("pattern", "TODO"), kwargs.get("path", "."))
            else:
                result = SkillResult.fail(f"Unknown code action: {action}")

            elapsed = (time.monotonic() - t0) * 1000
            result.metadata["duration_ms"] = round(elapsed, 1)
            return result
        except Exception as exc:
            return SkillResult.fail(f"Code analysis error: {exc}")

    def rollback(self, context: dict) -> SkillResult:
        return SkillResult.fail("Code analysis has no rollback")

    _EXCLUDE_DIRS = {"__pycache__", "node_modules", ".venv", "venv", ".git", ".aria", "egg-info", ".tox", ".mypy_cache", "site-packages", ".aider"}

    def _scan(self, path: str) -> SkillResult:
        import os
        base = Path(path).resolve()
        stats = {"total_files": 0, "python_files": 0, "total_lines": 0, "blank_lines": 0}
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in self._EXCLUDE_DIRS]
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fp = Path(root) / fname
                stats["total_files"] += 1
                stats["python_files"] += 1
                try:
                    lines = fp.read_text(encoding="utf-8", errors="replace").splitlines()
                    stats["total_lines"] += len(lines)
                    stats["blank_lines"] += sum(1 for l in lines if not l.strip())
                except Exception:
                    continue

        for f in base.rglob("*"):
            if f.suffix and f.suffix != ".py" and f.is_file():
                if "__pycache__" not in str(f) and "node_modules" not in str(f):
                    stats["total_files"] += 1

        return SkillResult.ok(output=json.dumps(stats, indent=2), **stats)

    def _complexity(self, path: str) -> SkillResult:
        import os
        base = Path(path).resolve()
        results = []
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in self._EXCLUDE_DIRS]
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fp = Path(root) / fname
                try:
                    source = fp.read_text(encoding="utf-8", errors="replace")
                    tree = ast.parse(source)
                    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
                    results.append({
                        "file": str(fp.relative_to(base)),
                        "functions": len(funcs),
                        "classes": len(classes),
                        "lines": len(source.splitlines()),
                    })
                except (SyntaxError, Exception):
                    continue

        return SkillResult.ok(output=json.dumps(results, indent=2), files_analyzed=len(results))

    def _structure(self, path: str) -> SkillResult:
        import os
        base = Path(path).resolve()
        modules = []
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in self._EXCLUDE_DIRS]
            for fname in sorted(files):
                if not fname.endswith(".py"):
                    continue
                fp = Path(root) / fname
                rel = str(fp.relative_to(base))
                try:
                    source = fp.read_text(encoding="utf-8", errors="replace")
                    tree = ast.parse(source)
                    exports = []
                    for node in ast.iter_child_nodes(tree):
                        if isinstance(node, ast.ClassDef):
                            exports.append(f"class {node.name}")
                        elif isinstance(node, ast.FunctionDef):
                            exports.append(f"def {node.name}")
                    if exports:
                        modules.append({"file": rel, "exports": exports})
                except (SyntaxError, Exception):
                    continue

        return SkillResult.ok(output=json.dumps(modules, indent=2), modules=len(modules))

    def _find_patterns(self, pattern: str, path: str) -> SkillResult:
        import os, re
        base = Path(path).resolve()
        regex = re.compile(pattern, re.IGNORECASE)
        matches = []
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in self._EXCLUDE_DIRS]
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fp = Path(root) / fname
                try:
                    for i, line in enumerate(fp.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                        if regex.search(line):
                            matches.append({"file": str(fp.relative_to(base)), "line": i, "text": line.strip()[:100]})
                except Exception:
                    continue

        return SkillResult.ok(output=json.dumps(matches, indent=2), matches=len(matches))


import json
