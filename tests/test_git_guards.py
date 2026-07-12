from __future__ import annotations

import pytest
from git_ops.guards import DestructiveGuard


class TestDestructiveGuard:
    def test_force_push_tool_is_destructive(self):
        guard = DestructiveGuard()
        assert guard.is_destructive("force_push", {}) is True

    def test_reset_hard_tool_is_destructive(self):
        guard = DestructiveGuard()
        assert guard.is_destructive("reset_hard", {}) is True

    def test_branch_delete_tool_is_destructive(self):
        guard = DestructiveGuard()
        assert guard.is_destructive("branch_delete", {}) is True

    def test_normal_tool_not_destructive(self):
        guard = DestructiveGuard()
        assert guard.is_destructive("read_file", {}) is False
        assert guard.is_destructive("git_status", {}) is False

    def test_force_push_in_command(self):
        guard = DestructiveGuard()
        assert guard.is_destructive("run_command", {"command": "git push --force origin main"}) is True

    def test_force_push_short_flag(self):
        guard = DestructiveGuard()
        assert guard.is_destructive("run_command", {"command": "git push -f origin main"}) is True

    def test_reset_hard_in_command(self):
        guard = DestructiveGuard()
        assert guard.is_destructive("run_command", {"command": "git reset --hard HEAD"}) is True

    def test_branch_delete_in_command(self):
        guard = DestructiveGuard()
        assert guard.is_destructive("run_command", {"command": "git branch -D feature"}) is True

    def test_clean_force_in_command(self):
        guard = DestructiveGuard()
        assert guard.is_destructive("run_command", {"command": "git clean -f"}) is True

    def test_normal_command_not_destructive(self):
        guard = DestructiveGuard()
        assert guard.is_destructive("run_command", {"command": "echo hello"}) is False
        assert guard.is_destructive("run_command", {"command": "git add file.py"}) is False

    def test_empty_command_not_destructive(self):
        guard = DestructiveGuard()
        assert guard.is_destructive("run_command", {}) is False
        assert guard.is_destructive("run_command", {"command": ""}) is False
