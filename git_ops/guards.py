from __future__ import annotations

import re


class DestructiveGuard:
    """Detects destructive git operations that should always be blocked."""

    DESTRUCTIVE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
        ("force_push", re.compile(r"push\s+--force", re.IGNORECASE)),
        ("force_push", re.compile(r"push\s+-f", re.IGNORECASE)),
        ("reset_hard", re.compile(r"reset\s+--hard", re.IGNORECASE)),
        ("branch_delete", re.compile(r"branch\s+(-d|-D)", re.IGNORECASE)),
        ("checkout_force", re.compile(r"checkout\s+--force", re.IGNORECASE)),
        ("clean_force", re.compile(r"clean\s+(-f|-fd|-fdx)", re.IGNORECASE)),
        ("rebase_hard", re.compile(r"rebase\s+--abort", re.IGNORECASE)),
    ]

    def is_destructive(self, tool_name: str, args: dict) -> bool:
        if tool_name in ("force_push", "reset_hard", "branch_delete"):
            return True

        command = args.get("command", "")
        if not command:
            return False

        for _label, pattern in self.DESTRUCTIVE_PATTERNS:
            if pattern.search(command):
                return True

        return False
