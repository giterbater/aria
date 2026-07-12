from __future__ import annotations

import pytest
from tools.file_editor import ApplyEditTool, CreateFileTool, DeleteFileTool


class TestApplyEditTool:
    def test_edit_success(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("hello world")
        tool = ApplyEditTool()
        result = tool.execute(path=str(f), old_string="hello", new_string="goodbye")
        assert result.success is True
        assert f.read_text() == "goodbye world"

    def test_edit_not_found(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("hello world")
        tool = ApplyEditTool()
        result = tool.execute(path=str(f), old_string="nonexistent", new_string="x")
        assert result.success is False

    def test_edit_multiple_matches(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("aaa bbb aaa")
        tool = ApplyEditTool()
        result = tool.execute(path=str(f), old_string="aaa", new_string="x")
        assert result.success is False
        assert "2 matches" in result.output

    def test_edit_nonexistent_file(self):
        tool = ApplyEditTool()
        result = tool.execute(path="/nonexistent/file.py", old_string="x", new_string="y")
        assert result.success is False


class TestCreateFileTool:
    def test_create_file(self, tmp_path):
        f = tmp_path / "new.py"
        tool = CreateFileTool()
        result = tool.execute(path=str(f), content="print('hello')")
        assert result.success is True
        assert f.read_text() == "print('hello')"

    def test_create_with_dirs(self, tmp_path):
        f = tmp_path / "sub" / "deep" / "new.py"
        tool = CreateFileTool()
        result = tool.execute(path=str(f), content="x")
        assert result.success is True
        assert f.exists()

    def test_create_existing(self, tmp_path):
        f = tmp_path / "existing.py"
        f.write_text("old")
        tool = CreateFileTool()
        result = tool.execute(path=str(f), content="new")
        assert result.success is False


class TestDeleteFileTool:
    def test_delete_file(self, tmp_path):
        f = tmp_path / "to_delete.py"
        f.write_text("bye")
        tool = DeleteFileTool()
        result = tool.execute(path=str(f))
        assert result.success is True
        assert not f.exists()

    def test_delete_nonexistent(self):
        tool = DeleteFileTool()
        result = tool.execute(path="/nonexistent/file.py")
        assert result.success is False

    def test_delete_not_a_file(self, tmp_path):
        tool = DeleteFileTool()
        result = tool.execute(path=str(tmp_path))
        assert result.success is False

    def test_is_destructive(self):
        tool = DeleteFileTool()
        assert tool.destructive is True
