from __future__ import annotations

import pytest
from tools.repo_tools import ListFilesTool, GetStructureTool, ReadFileTool, SearchCodeTool


class TestListFilesTool:
    def test_list_existing_dir(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1")
        (tmp_path / "b.py").write_text("y = 2")
        (tmp_path / "sub").mkdir()
        tool = ListFilesTool()
        result = tool.execute(path=str(tmp_path))
        assert result.success is True
        assert "a.py" in result.output
        assert "b.py" in result.output
        assert "sub/" in result.output

    def test_list_nonexistent(self):
        tool = ListFilesTool()
        result = tool.execute(path="/nonexistent/path/xyz")
        assert result.success is False

    def test_list_recursive(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.py").write_text("z = 3")
        (tmp_path / "top.py").write_text("a = 1")
        tool = ListFilesTool()
        result = tool.execute(path=str(tmp_path), recursive=True)
        assert "top.py" in result.output
        assert "deep.py" in result.output

    def test_list_with_pattern(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        (tmp_path / "b.txt").write_text("y")
        tool = ListFilesTool()
        result = tool.execute(path=str(tmp_path), pattern="*.py")
        assert "a.py" in result.output
        assert "b.txt" not in result.output

    def test_list_file_not_dir(self, tmp_path):
        f = tmp_path / "file.py"
        f.write_text("x")
        tool = ListFilesTool()
        result = tool.execute(path=str(f))
        assert result.success is False


class TestGetStructureTool:
    def test_structure(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        sub = tmp_path / "pkg"
        sub.mkdir()
        (sub / "b.py").write_text("y")
        tool = GetStructureTool()
        result = tool.execute(path=str(tmp_path), max_depth=2)
        assert result.success is True
        assert "a.py" in result.output
        assert "pkg/" in result.output
        assert "b.py" in result.output

    def test_structure_nonexistent(self):
        tool = GetStructureTool()
        result = tool.execute(path="/nonexistent")
        assert result.success is False

    def test_structure_max_depth(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        deep = tmp_path / "l1" / "l2" / "l3"
        deep.mkdir(parents=True)
        (deep / "deep.py").write_text("y")
        tool = GetStructureTool()
        result = tool.execute(path=str(tmp_path), max_depth=1)
        assert "l1/" in result.output
        assert "l2/" not in result.output


class TestReadFileTool:
    def test_read_file(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("line1\nline2\nline3")
        tool = ReadFileTool()
        result = tool.execute(path=str(f))
        assert result.success is True
        assert "1: line1" in result.output
        assert "2: line2" in result.output

    def test_read_with_offset_limit(self, tmp_path):
        f = tmp_path / "big.py"
        lines = [f"line{i}" for i in range(100)]
        f.write_text("\n".join(lines))
        tool = ReadFileTool()
        result = tool.execute(path=str(f), offset=50, limit=5)
        assert "51: line50" in result.output
        assert "55: line54" in result.output

    def test_read_nonexistent(self):
        tool = ReadFileTool()
        result = tool.execute(path="/nonexistent/file.py")
        assert result.success is False

    def test_read_not_a_file(self, tmp_path):
        tool = ReadFileTool()
        result = tool.execute(path=str(tmp_path))
        assert result.success is False


class TestSearchCodeTool:
    def test_search_found(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("def hello():\n    pass\ndef world():\n    pass")
        tool = SearchCodeTool()
        result = tool.execute(pattern="def \\w+", path=str(f))
        assert result.success is True
        assert "hello" in result.output
        assert "world" in result.output

    def test_search_not_found(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("x = 1")
        tool = SearchCodeTool()
        result = tool.execute(pattern="nonexistent_pattern_xyz", path=str(f))
        assert result.success is True
        assert "(no matches)" in result.output

    def test_search_invalid_regex(self):
        tool = SearchCodeTool()
        result = tool.execute(pattern="[invalid", path=".")
        assert result.success is False

    def test_search_nonexistent_path(self):
        tool = SearchCodeTool()
        result = tool.execute(pattern="test", path="/nonexistent")
        assert result.success is False
