from __future__ import annotations

import os
import subprocess
import pytest
from aria_core.skills.builtin import FileSkill, TerminalSkill, GitSkill


class TestFileSkill:
    def test_read_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello\nworld")
        skill = FileSkill(base_path=str(tmp_path))
        result = skill.execute(action="read", path="test.txt")
        assert result.success is True
        assert "hello" in result.output

    def test_write_file(self, tmp_path):
        skill = FileSkill(base_path=str(tmp_path))
        result = skill.execute(action="write", path="new.txt", content="data")
        assert result.success is True
        assert (tmp_path / "new.txt").read_text() == "data"

    def test_create_file(self, tmp_path):
        skill = FileSkill(base_path=str(tmp_path))
        result = skill.execute(action="create", path="created.txt", content="x")
        assert result.success is True
        assert (tmp_path / "created.txt").exists()

    def test_create_existing_fails(self, tmp_path):
        (tmp_path / "exists.txt").write_text("x")
        skill = FileSkill(base_path=str(tmp_path))
        result = skill.execute(action="create", path="exists.txt", content="y")
        assert result.success is False

    def test_edit_file(self, tmp_path):
        f = tmp_path / "edit.txt"
        f.write_text("hello world")
        skill = FileSkill(base_path=str(tmp_path))
        result = skill.execute(action="edit", path="edit.txt", old_string="hello", new_string="goodbye")
        assert result.success is True
        assert f.read_text() == "goodbye world"

    def test_edit_not_found(self, tmp_path):
        skill = FileSkill(base_path=str(tmp_path))
        result = skill.execute(action="edit", path="no.txt", old_string="a", new_string="b")
        assert result.success is False

    def test_edit_multiple_matches(self, tmp_path):
        f = tmp_path / "dup.txt"
        f.write_text("aaa bbb aaa")
        skill = FileSkill(base_path=str(tmp_path))
        result = skill.execute(action="edit", path="dup.txt", old_string="aaa", new_string="x")
        assert result.success is False

    def test_delete_file(self, tmp_path):
        f = tmp_path / "del.txt"
        f.write_text("bye")
        skill = FileSkill(base_path=str(tmp_path))
        result = skill.execute(action="delete", path="del.txt")
        assert result.success is True
        assert not f.exists()

    def test_list_files(self, tmp_path):
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        skill = FileSkill(base_path=str(tmp_path))
        result = skill.execute(action="list", path=".")
        assert result.success is True
        assert "a.txt" in result.output

    def test_read_nonexistent(self, tmp_path):
        skill = FileSkill(base_path=str(tmp_path))
        result = skill.execute(action="read", path="nope.txt")
        assert result.success is False

    def test_validate(self, tmp_path):
        (tmp_path / "v.txt").write_text("x")
        skill = FileSkill(base_path=str(tmp_path))
        assert skill.validate(action="read", path="v.txt") is True
        assert skill.validate(action="read", path="missing.txt") is False
        assert skill.validate(action="write", path="new.txt") is True

    def test_move_file(self, tmp_path):
        f = tmp_path / "src.txt"
        f.write_text("content")
        skill = FileSkill(base_path=str(tmp_path))
        result = skill.execute(action="move", path="src.txt", destination="dst.txt")
        assert result.success is True
        assert not f.exists()
        assert (tmp_path / "dst.txt").read_text() == "content"


class TestTerminalSkill:
    def test_execute_echo(self):
        skill = TerminalSkill()
        result = skill.execute(command="echo hello")
        assert result.success is True
        assert "hello" in result.output

    def test_execute_failing(self):
        skill = TerminalSkill()
        result = skill.execute(command="python -c \"import sys; sys.exit(1)\"")
        assert result.success is False

    def test_execute_with_cwd(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("content")
        skill = TerminalSkill()
        cmd = "type test.txt" if os.name == "nt" else "cat test.txt"
        result = skill.execute(command=cmd, cwd=str(tmp_path))
        assert result.success is True

    def test_timeout(self):
        skill = TerminalSkill()
        result = skill.execute(command="python -c \"import time; time.sleep(10)\"", timeout=1)
        assert result.success is False
        assert any("timed out" in e for e in result.errors)

    def test_validate(self):
        skill = TerminalSkill()
        assert skill.validate(command="echo hi") is True
        assert skill.validate(command="") is False

    def test_metadata(self):
        skill = TerminalSkill()
        result = skill.execute(command="echo test")
        assert "returncode" in result.metadata
        assert "elapsed" in result.metadata


class TestGitSkill:
    def test_status(self, tmp_path):
        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        skill = GitSkill(default_cwd=str(tmp_path))
        result = skill.execute(action="status")
        assert result.success is True

    def test_commit(self, tmp_path):
        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), capture_output=True)
        (tmp_path / "file.txt").write_text("x")
        skill = GitSkill(default_cwd=str(tmp_path))
        skill.execute(action="add", paths=["file.txt"])
        result = skill.execute(action="commit", message="initial")
        assert result.success is True

    def test_log(self, tmp_path):
        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), capture_output=True)
        (tmp_path / "f.txt").write_text("x")
        skill = GitSkill(default_cwd=str(tmp_path))
        skill.execute(action="add", paths=["f.txt"])
        skill.execute(action="commit", message="init")
        result = skill.execute(action="log")
        assert result.success is True

    def test_commit_no_message(self, tmp_path):
        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        skill = GitSkill(default_cwd=str(tmp_path))
        result = skill.execute(action="commit")
        assert result.success is False

    def test_branch_list(self, tmp_path):
        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        skill = GitSkill(default_cwd=str(tmp_path))
        result = skill.execute(action="branch")
        assert result.success is True

    def test_diff_clean(self, tmp_path):
        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        skill = GitSkill(default_cwd=str(tmp_path))
        result = skill.execute(action="diff")
        assert result.success is True

    def test_validate(self):
        skill = GitSkill()
        assert skill.validate(action="status") is True
        assert skill.validate(action="unknown") is False
