from __future__ import annotations

import time
from pathlib import Path

from ..interfaces import Skill, SkillResult, SkillMeta


class DocSkill:
    """Documentation generation: README, markdown, API docs."""

    def __init__(self, base_path: str | None = None) -> None:
        self._base = Path(base_path).resolve() if base_path else Path.cwd()

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="documentation",
            description="Generate and update documentation",
            category="docs",
            tags=["documentation", "readme", "markdown", "api", "docs"],
            timeout_seconds=15.0,
        )

    def validate(self, action: str = "generate_readme", **kwargs) -> bool:
        return action in ("generate_readme", "update_changelog", "generate_api_doc", "list_docs")

    def execute(self, action: str = "generate_readme", **kwargs) -> SkillResult:
        t0 = time.monotonic()
        try:
            if action == "generate_readme":
                result = self._generate_readme(kwargs.get("project_name", "Project"), kwargs.get("description", ""))
            elif action == "update_changelog":
                result = self._update_changelog(kwargs.get("entry", ""))
            elif action == "generate_api_doc":
                result = self._generate_api_doc(kwargs.get("module_path", ""))
            elif action == "list_docs":
                result = self._list_docs()
            else:
                result = SkillResult.fail(f"Unknown doc action: {action}")

            elapsed = (time.monotonic() - t0) * 1000
            result.metadata["duration_ms"] = round(elapsed, 1)
            return result
        except Exception as exc:
            return SkillResult.fail(f"Documentation error: {exc}")

    def rollback(self, context: dict) -> SkillResult:
        return SkillResult.fail("Documentation rollback not supported")

    def _generate_readme(self, name: str, description: str) -> SkillResult:
        readme_path = self._base / "README.md"
        content = f"# {name}\n\n{description}\n\n## Installation\n\n```bash\npip install {name.lower().replace(' ', '-')}\n```\n\n## Usage\n\nSee documentation.\n"
        readme_path.write_text(content, encoding="utf-8")
        return SkillResult.ok(output=f"Generated README.md for {name}", path=str(readme_path))

    def _update_changelog(self, entry: str) -> SkillResult:
        if not entry:
            return SkillResult.fail("changelog entry is required")
        changelog_path = self._base / "CHANGELOG.md"
        existing = changelog_path.read_text(encoding="utf-8") if changelog_path.exists() else "# Changelog\n\n"
        new_content = existing + f"- {entry}\n"
        changelog_path.write_text(new_content, encoding="utf-8")
        return SkillResult.ok(output=f"Updated CHANGELOG.md", path=str(changelog_path))

    def _generate_api_doc(self, module_path: str) -> SkillResult:
        if not module_path:
            return SkillResult.fail("module_path is required")
        p = Path(module_path)
        if not p.exists():
            return SkillResult.fail(f"Module not found: {module_path}")

        lines = [f"# API: {p.stem}\n"]
        content = p.read_text(encoding="utf-8", errors="replace")
        for line in content.splitlines():
            if line.startswith("def ") or line.startswith("class "):
                lines.append(f"## `{line.strip()}`\n")

        doc_path = self._base / "docs" / f"{p.stem}_api.md"
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text("\n".join(lines), encoding="utf-8")
        return SkillResult.ok(output=f"Generated API doc for {module_path}", path=str(doc_path))

    def _list_docs(self) -> SkillResult:
        docs = []
        for ext in ("*.md", "*.rst", "*.txt"):
            for f in self._base.rglob(ext):
                if "node_modules" not in str(f) and "__pycache__" not in str(f):
                    docs.append(str(f.relative_to(self._base)))
        return SkillResult.ok(output="\n".join(docs), count=len(docs))
