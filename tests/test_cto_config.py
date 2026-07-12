from __future__ import annotations

import pytest
from cto.config import CTOConfig
from pathlib import Path


class TestCTOConfig:
    def test_defaults(self):
        config = CTOConfig(repo_path=".")
        assert config.model == "minimaxai/minimax-m2.7"
        assert config.ollama_base_url == "http://localhost:11434"
        assert config.cycle_interval_seconds == 30
        assert config.max_review_retries == 3
        assert config.auto_approve is False
        assert config.single_cycle is False
        assert config.max_cycles is None

    def test_repo_path_resolved(self, tmp_path):
        config = CTOConfig(repo_path=str(tmp_path))
        resolved = config.repo_path_resolved()
        assert isinstance(resolved, Path)
        assert resolved.exists()

    def test_permissions_default_keys(self):
        config = CTOConfig(repo_path=".")
        expected_keys = {
            "read_file", "list_files", "search_code", "get_structure",
            "git_status", "git_diff", "git_log", "git_add", "git_commit",
            "apply_edit", "create_file", "delete_file", "rename_file",
            "run_command", "run_tests", "git_push", "git_branch_create",
            "git_branch_delete", "git_reset_hard", "git_force_push",
        }
        assert set(config.permissions.keys()) == expected_keys

    def test_auto_tools_are_auto(self):
        config = CTOConfig(repo_path=".")
        for tool in ["read_file", "list_files", "search_code", "git_status", "run_tests"]:
            assert config.permissions[tool] == "auto"

    def test_block_tools_are_block(self):
        config = CTOConfig(repo_path=".")
        for tool in ["git_branch_delete", "git_reset_hard", "git_force_push"]:
            assert config.permissions[tool] == "block"
