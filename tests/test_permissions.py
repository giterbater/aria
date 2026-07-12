from __future__ import annotations

import pytest
from permissions.tiered_model import TieredPermissionPolicy
from permissions.interfaces import PermissionTier


class TestTieredPermissionPolicy:
    def test_auto_tools(self):
        policy = TieredPermissionPolicy({"read_file": "auto", "git_status": "auto"})
        assert policy.tier_for("read_file", {}) == PermissionTier.AUTO
        assert policy.tier_for("git_status", {}) == PermissionTier.AUTO

    def test_ask_tools(self):
        policy = TieredPermissionPolicy({"apply_edit": "ask"})
        assert policy.tier_for("apply_edit", {}) == PermissionTier.ASK

    def test_block_tools(self):
        policy = TieredPermissionPolicy({"git_force_push": "block"})
        assert policy.tier_for("git_force_push", {}) == PermissionTier.BLOCK

    def test_destructive_guard_overrides_config(self):
        policy = TieredPermissionPolicy({"force_push": "auto"})
        assert policy.tier_for("force_push", {}) == PermissionTier.BLOCK

    def test_destructive_command_override(self):
        policy = TieredPermissionPolicy({"run_command": "auto"})
        assert policy.tier_for("run_command", {"command": "git push --force"}) == PermissionTier.BLOCK

    def test_is_allowed(self):
        policy = TieredPermissionPolicy({"read_file": "auto", "apply_edit": "ask"})
        assert policy.is_allowed("read_file", {}) is True
        assert policy.is_allowed("apply_edit", {}) is True
        assert policy.is_allowed("force_push", {}) is False

    def test_requires_approval(self):
        policy = TieredPermissionPolicy({"read_file": "auto", "apply_edit": "ask"})
        assert policy.requires_approval("read_file", {}) is False
        assert policy.requires_approval("apply_edit", {}) is True

    def test_is_blocked(self):
        policy = TieredPermissionPolicy({"force_push": "block"})
        assert policy.is_blocked("force_push", {}) is True
        assert policy.is_blocked("read_file", {}) is False

    def test_unknown_tool_defaults_to_ask(self):
        policy = TieredPermissionPolicy({})
        assert policy.tier_for("some_unknown_tool", {}) == PermissionTier.ASK

    def test_invalid_tier_defaults_to_ask(self):
        policy = TieredPermissionPolicy({"tool": "invalid_tier"})
        assert policy.tier_for("tool", {}) == PermissionTier.ASK
