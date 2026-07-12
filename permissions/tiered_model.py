from __future__ import annotations

import logging
from typing import Dict

from .interfaces import PermissionTier

logger = logging.getLogger("aria.cto.permissions")

try:
    from git_ops.guards import DestructiveGuard
except ImportError:
    from git_ops.guards import DestructiveGuard  # type: ignore[no-redef]


class TieredPermissionPolicy:
    """Permission policy driven by CTOConfig.permissions + destructive guard."""

    def __init__(self, permissions: Dict[str, str]) -> None:
        self._tiers: Dict[str, PermissionTier] = {}
        for name, tier_str in permissions.items():
            try:
                self._tiers[name] = PermissionTier(tier_str)
            except ValueError:
                logger.warning("Invalid permission tier %r for %s, defaulting to ASK", tier_str, name)
                self._tiers[name] = PermissionTier.ASK
        self._guard = DestructiveGuard()

    def tier_for(self, tool_name: str, args: dict) -> PermissionTier:
        if self._guard.is_destructive(tool_name, args):
            return PermissionTier.BLOCK
        return self._tiers.get(tool_name, PermissionTier.ASK)

    def is_allowed(self, tool_name: str, args: dict) -> bool:
        tier = self.tier_for(tool_name, args)
        return tier in (PermissionTier.AUTO, PermissionTier.ASK)

    def requires_approval(self, tool_name: str, args: dict) -> bool:
        return self.tier_for(tool_name, args) == PermissionTier.ASK

    def is_blocked(self, tool_name: str, args: dict) -> bool:
        return self.tier_for(tool_name, args) == PermissionTier.BLOCK
