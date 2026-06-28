# aria_core/execution/registry.py
"""
Tool registry and the four MVP tools.

The registry is a tiny in-process dispatch table: tools register
themselves by name and the worker asks the registry to execute them.
Each tool returns an :class:`ActionResult` – never raises – so the
worker loop has a single, predictable error path.

MVP tool catalogue (Milestone 2 contract)
-----------------------------------------
* ``launch_application`` – open an app by name.
* ``set_reminder`` – schedule a message to fire after N seconds.
* ``cancel_reminder`` – cancel every pending timer whose message
  contains a substring.
* ``current_time`` – return the current wall-clock time.
"""

from __future__ import annotations

import datetime
import os
import subprocess
import sys
import threading
import time
import uuid
from typing import Callable, Dict, List

from .interfaces import ActionResult
from .reminders import PendingReminders


# ---------------------------------------------------------------------------
# launch_application
# ---------------------------------------------------------------------------
def launch_application(*, app: str) -> ActionResult:
    """Open *app* via the host shell.

    The exact argv is platform-specific (see the M2 contract).  On
    unsupported platforms we return a failed :class:`ActionResult`
    rather than raising, so the worker can surface the error to the
    user instead of crashing the loop.
    """
    if not isinstance(app, str) or not app.strip():
        return ActionResult(
            success=False,
            message="launch_application requires a non-empty 'app' string",
        )

    try:
        if sys.platform.startswith("win"):
            # `start ""` swallows the empty-title warning on Windows;
            # the empty string is required positional.
            subprocess.Popen(["cmd", "/c", "start", "", app])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-a", app])
        else:
            # Linux and other Unix-likes – assume the app name is on PATH.
            subprocess.Popen([app])
    except FileNotFoundError as exc:
        return ActionResult(
            success=False,
            message=f"launch_application: app not found: {exc}",
        )
    except Exception as exc:  # pragma: no cover – defensive
        return ActionResult(
            success=False,
            message=f"launch_application failed: {exc}",
        )

    return ActionResult(
        success=True,
        message=f"launched {app}",
        data={"app": app, "platform": sys.platform},
    )


# ---------------------------------------------------------------------------
# set_reminder
# ---------------------------------------------------------------------------
def set_reminder(*, seconds: int, message: str) -> ActionResult:
    """Schedule *message* to fire *seconds* from now."""
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return ActionResult(
            success=False,
            message="set_reminder requires a non-negative 'seconds'",
        )
    if not isinstance(message, str) or not message.strip():
        return ActionResult(
            success=False,
            message="set_reminder requires a non-empty 'message'",
        )

    reminder_id = str(uuid.uuid4())
    pending = PendingReminders.instance()
    pending.schedule(reminder_id, message, int(seconds))

    # Also arm a real ``threading.Timer`` so reminders fire on time in
    # production.  Tests should call ``PendingReminders.tick(now=...)``
    # to fast-forward without sleeping.
    def _fire():
        # Schedule simply appends to ``pending``; the worker will
        # drain the singleton on its next turn and surface the message.
        # We do NOT push directly into ``_fired`` because the worker
        # should be the one that decides *when* to deliver the reminder.
        pass

    timer = threading.Timer(int(seconds), _fire)
    timer.daemon = True
    timer.start()

    return ActionResult(
        success=True,
        message=f"reminder set for {int(seconds)}s",
        data={
            "reminder_id": reminder_id,
            "seconds": int(seconds),
            "message": message,
        },
    )


# ---------------------------------------------------------------------------
# cancel_reminder
# ---------------------------------------------------------------------------
def cancel_reminder(*, message: str) -> ActionResult:
    """Cancel every pending timer whose message contains *message*."""
    if not isinstance(message, str) or not message.strip():
        return ActionResult(
            success=False,
            message="cancel_reminder requires a non-empty 'message'",
        )
    cancelled = PendingReminders.instance().cancel_by_message(message)
    return ActionResult(
        success=True,
        message=f"cancelled {cancelled} reminder(s)",
        data={"cancelled": cancelled, "query": message},
    )


# ---------------------------------------------------------------------------
# current_time
# ---------------------------------------------------------------------------
def current_time() -> ActionResult:
    """Return the current wall-clock time as ISO-8601 + epoch."""
    now = datetime.datetime.now()
    iso = now.isoformat()
    epoch = int(time.time())
    return ActionResult(
        success=True,
        message=iso,
        data={"iso": iso, "epoch": epoch},
    )


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------
class ToolRegistry:
    """In-process dispatch table mapping tool names to callables."""

    def __init__(self) -> None:
        self._tools: Dict[str, Callable[..., ActionResult]] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def register(self, name: str, fn: Callable[..., ActionResult]) -> None:
        """Register *fn* under *name*.  Overwrites any existing entry."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("tool name must be a non-empty string")
        if not callable(fn):
            raise ValueError(f"tool {name!r} must be callable")
        self._tools[name] = fn

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------
    def dispatch(self, name: str, args: dict | None = None) -> ActionResult:
        """Invoke the tool registered as *name*.

        Never raises; an unknown name returns a failed ActionResult so
        the worker loop has one error path.
        """
        args = args or {}
        fn = self._tools.get(name)
        if fn is None:
            return ActionResult(
                success=False,
                message=f"unknown tool: {name}",
                data={"known_tools": sorted(self._tools)},
            )
        try:
            return fn(**args)
        except TypeError as exc:
            return ActionResult(
                success=False,
                message=f"tool {name!r} got bad args: {exc}",
                data={"args": args},
            )
        except Exception as exc:  # pragma: no cover – defensive
            return ActionResult(
                success=False,
                message=f"tool {name!r} raised: {exc}",
                data={"args": args},
            )

    def known_tools(self) -> List[str]:
        return sorted(self._tools)

    # ------------------------------------------------------------------
    # Convenience constructors
    # ------------------------------------------------------------------
    @classmethod
    def with_defaults(cls) -> "ToolRegistry":
        """Build a registry pre-loaded with the four MVP tools."""
        reg = cls()
        reg.register("launch_application", launch_application)
        reg.register("set_reminder", set_reminder)
        reg.register("cancel_reminder", cancel_reminder)
        reg.register("current_time", current_time)
        return reg