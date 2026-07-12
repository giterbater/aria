from __future__ import annotations

import subprocess
import pytest
from git_ops.operations import GitOperationsImpl


@pytest.fixture
def git_repo(tmp_path):
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), capture_output=True)
    return tmp_path


class TestGitOperations:
    def test_status_clean(self, git_repo):
        ops = GitOperationsImpl()
        result = ops.status(str(git_repo))
        assert result.success is True
        assert "(clean working tree)" in result.output

    def test_status_dirty(self, git_repo):
        (git_repo / "file.py").write_text("x = 1")
        ops = GitOperationsImpl()
        result = ops.status(str(git_repo))
        assert result.success is True
        assert "file.py" in result.output

    def test_add_and_commit(self, git_repo):
        (git_repo / "file.py").write_text("x = 1")
        ops = GitOperationsImpl()
        add_result = ops.add(str(git_repo), ["file.py"])
        assert add_result.success is True
        commit_result = ops.commit(str(git_repo), "initial commit")
        assert commit_result.success is True

    def test_diff_clean(self, git_repo):
        (git_repo / "file.py").write_text("x = 1")
        ops = GitOperationsImpl()
        ops.add(str(git_repo), ["file.py"])
        ops.commit(str(git_repo), "init")
        result = ops.diff(str(git_repo))
        assert result.success is True

    def test_log(self, git_repo):
        (git_repo / "file.py").write_text("x = 1")
        ops = GitOperationsImpl()
        ops.add(str(git_repo), ["file.py"])
        ops.commit(str(git_repo), "init")
        result = ops.log(str(git_repo))
        assert result.success is True
        assert "init" in result.output

    def test_branch_list(self, git_repo):
        ops = GitOperationsImpl()
        result = ops.branch_list(str(git_repo))
        assert result.success is True

    def test_branch_create(self, git_repo):
        (git_repo / "file.py").write_text("x = 1")
        ops = GitOperationsImpl()
        ops.add(str(git_repo), ["file.py"])
        ops.commit(str(git_repo), "init")
        result = ops.branch_create(str(git_repo), "feature-1")
        assert result.success is True

    def test_commit_empty_message(self, git_repo):
        ops = GitOperationsImpl()
        result = ops.commit(str(git_repo), "  ")
        assert result.success is False

    def test_add_no_paths(self, git_repo):
        ops = GitOperationsImpl()
        result = ops.add(str(git_repo), [])
        assert result.success is False
