from __future__ import annotations

import pytest
from aria_core.skills.builtin.doc_skill import DocSkill
from aria_core.skills.builtin.web_skill import WebResearchSkill
from aria_core.skills.builtin.code_skill import CodeSkill


class TestDocSkill:
    def test_generate_readme(self, tmp_path):
        skill = DocSkill(base_path=str(tmp_path))
        result = skill.execute(action="generate_readme", project_name="TestApp", description="A test app")
        assert result.success is True
        assert (tmp_path / "README.md").exists()

    def test_update_changelog(self, tmp_path):
        skill = DocSkill(base_path=str(tmp_path))
        result = skill.execute(action="update_changelog", entry="Added feature X")
        assert result.success is True
        assert "Added feature X" in (tmp_path / "CHANGELOG.md").read_text()

    def test_update_changelog_empty(self, tmp_path):
        skill = DocSkill(base_path=str(tmp_path))
        result = skill.execute(action="update_changelog", entry="")
        assert result.success is False

    def test_generate_api_doc(self, tmp_path):
        f = tmp_path / "module.py"
        f.write_text("class MyClass:\n    def method(self): pass\ndef helper(): pass")
        skill = DocSkill(base_path=str(tmp_path))
        result = skill.execute(action="generate_api_doc", module_path=str(f))
        assert result.success is True
        assert (tmp_path / "docs" / "module_api.md").exists()

    def test_generate_api_doc_missing(self, tmp_path):
        skill = DocSkill(base_path=str(tmp_path))
        result = skill.execute(action="generate_api_doc", module_path="")
        assert result.success is False

    def test_list_docs(self, tmp_path):
        (tmp_path / "README.md").write_text("# Test")
        (tmp_path / "CHANGELOG.md").write_text("# Changelog")
        skill = DocSkill(base_path=str(tmp_path))
        result = skill.execute(action="list_docs")
        assert result.success is True
        assert result.metadata["count"] == 2

    def test_validate(self):
        skill = DocSkill()
        assert skill.validate(action="generate_readme") is True
        assert skill.validate(action="unknown") is False


class TestWebResearchSkill:
    def test_summarize(self):
        skill = WebResearchSkill()
        text = "First sentence. Second sentence. Third sentence. Fourth. Fifth."
        result = skill.execute(action="summarize", text=text)
        assert result.success is True
        assert "First sentence" in result.output

    def test_summarize_short(self):
        skill = WebResearchSkill()
        result = skill.execute(action="summarize", text="Short text.")
        assert result.success is True
        assert result.output == "Short text."

    def test_validate(self):
        skill = WebResearchSkill()
        assert skill.validate(action="fetch", url="http://example.com") is True
        assert skill.validate(action="fetch") is False
        assert skill.validate(action="summarize", text="x") is True


class TestCodeSkill:
    def test_scan(self):
        skill = CodeSkill(base_path=".")
        result = skill.execute(action="scan", path="aria_core")
        assert result.success is True
        assert result.metadata["python_files"] > 0

    def test_complexity(self):
        skill = CodeSkill(base_path=".")
        result = skill.execute(action="complexity", path="aria_core")
        assert result.success is True
        assert result.metadata["files_analyzed"] > 0

    def test_structure(self):
        skill = CodeSkill(base_path=".")
        result = skill.execute(action="structure", path="aria_core")
        assert result.success is True
        assert result.metadata["modules"] > 0

    def test_find_patterns(self):
        skill = CodeSkill(base_path=".")
        result = skill.execute(action="find_patterns", pattern="TODO", path="aria_core")
        assert result.success is True

    def test_validate(self):
        skill = CodeSkill()
        assert skill.validate(action="scan") is True
        assert skill.validate(action="unknown") is False
