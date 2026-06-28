"""
Tests for the four MVP tools and the ToolRegistry.

``launch_application`` is exercised by mocking ``subprocess.Popen``
so no real Notepad process is started.  ``set_reminder`` is exercised
through the ``PendingReminders.tick(now=...)`` test seam so tests do
not need to wait on ``threading.Timer``.
"""

import datetime
import os
import subprocess
import sys
import unittest
from unittest.mock import patch, MagicMock

from aria_core.execution.interfaces import ActionResult, ActionExecutor
from aria_core.execution.registry import (
    ToolRegistry,
    cancel_reminder,
    current_time,
    launch_application,
    set_reminder,
)
from aria_core.execution.reminders import PendingReminders, PendingReminder


class StubExecutor(ActionExecutor):
    """Test helper – records every execute call and returns canned results."""

    def __init__(self, result: ActionResult | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._result = result or ActionResult(success=True, message="ok")

    def execute(self, *, tool_name: str, tool_args: dict) -> ActionResult:
        self.calls.append((tool_name, dict(tool_args)))
        return self._result


class TestCurrentTime(unittest.TestCase):
    def test_current_time_returns_iso_and_epoch(self):
        res = current_time()
        self.assertTrue(res.success)
        # ISO-8601 round-trip
        datetime.datetime.fromisoformat(res.message)
        self.assertIn("iso", res.data)
        self.assertIn("epoch", res.data)
        self.assertIsInstance(res.data["epoch"], int)


class TestLaunchApplication(unittest.TestCase):
    @patch("aria_core.execution.registry.subprocess.Popen")
    def test_launch_application_windows(self, mock_popen):
        with patch("aria_core.execution.registry.sys.platform", "win32"):
            res = launch_application(app="notepad")
        self.assertTrue(res.success)
        self.assertEqual(res.data["app"], "notepad")
        self.assertEqual(res.data["platform"], "win32")
        mock_popen.assert_called_once()
        argv = mock_popen.call_args[0][0]
        self.assertEqual(argv, ["cmd", "/c", "start", "", "notepad"])

    @patch("aria_core.execution.registry.subprocess.Popen")
    def test_launch_application_macos(self, mock_popen):
        with patch("aria_core.execution.registry.sys.platform", "darwin"):
            res = launch_application(app="TextEdit")
        self.assertTrue(res.success)
        argv = mock_popen.call_args[0][0]
        self.assertEqual(argv, ["open", "-a", "TextEdit"])

    @patch("aria_core.execution.registry.subprocess.Popen")
    def test_launch_application_linux(self, mock_popen):
        with patch("aria_core.execution.registry.sys.platform", "linux"):
            res = launch_application(app="xterm")
        self.assertTrue(res.success)
        argv = mock_popen.call_args[0][0]
        self.assertEqual(argv, ["xterm"])

    @patch("aria_core.execution.registry.subprocess.Popen")
    def test_launch_application_propagates_failure(self, mock_popen):
        mock_popen.side_effect = FileNotFoundError("nope")
        res = launch_application(app="ghost")
        self.assertFalse(res.success)
        self.assertIn("not found", res.message)

    def test_launch_application_rejects_empty_app(self):
        res = launch_application(app="")
        self.assertFalse(res.success)

    def test_launch_application_rejects_non_string(self):
        res = launch_application(app=42)  # type: ignore[arg-type]
        self.assertFalse(res.success)


class TestRemindersTool(unittest.TestCase):
    def setUp(self):
        PendingReminders.reset()

    def tearDown(self):
        PendingReminders.reset()

    def test_set_then_tick_fires_reminder(self):
        # Schedule with a 5-second deadline, then fast-forward past it.
        # Use a far-future timestamp so we don't race the wall clock.
        res = set_reminder(seconds=5, message="stretch")
        self.assertTrue(res.success)
        self.assertEqual(PendingReminders.instance().pending_count(), 1)

        far_future = 9_999_999_999.0  # year ~2286
        fired = PendingReminders.instance().tick(now=far_future)
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0].message, "stretch")

    def test_cancel_by_substring(self):
        set_reminder(seconds=10, message="drink water")
        set_reminder(seconds=20, message="stretch legs")
        set_reminder(seconds=30, message="look away")
        res = cancel_reminder(message="stretch")
        self.assertTrue(res.success)
        self.assertIn("cancelled 1 reminder(s)", res.message)
        self.assertEqual(res.data["cancelled"], 1)
        self.assertEqual(PendingReminders.instance().pending_count(), 2)

    def test_set_rejects_negative_seconds(self):
        res = set_reminder(seconds=-1, message="x")
        self.assertFalse(res.success)

    def test_set_rejects_empty_message(self):
        res = set_reminder(seconds=5, message="")
        self.assertFalse(res.success)

    def test_cancel_rejects_empty_message(self):
        res = cancel_reminder(message="")
        self.assertFalse(res.success)


class TestToolRegistry(unittest.TestCase):
    def setUp(self):
        PendingReminders.reset()

    def tearDown(self):
        PendingReminders.reset()

    def test_with_defaults_registers_all_four(self):
        reg = ToolRegistry.with_defaults()
        self.assertEqual(
            set(reg.known_tools()),
            {"launch_application", "set_reminder", "cancel_reminder", "current_time"},
        )

    def test_register_and_dispatch_custom_tool(self):
        reg = ToolRegistry()
        sentinel = ActionResult(success=True, message="custom")
        reg.register("custom", lambda: sentinel)
        out = reg.dispatch("custom", {})
        self.assertEqual(out, sentinel)

    def test_dispatch_unknown_returns_failed(self):
        reg = ToolRegistry()
        out = reg.dispatch("nope", {})
        self.assertFalse(out.success)
        self.assertIn("unknown tool", out.message)

    def test_dispatch_bad_args_returns_failed(self):
        reg = ToolRegistry()
        reg.register("needs_kwargs", lambda *, x: ActionResult(True, str(x)))
        out = reg.dispatch("needs_kwargs", {"y": 1})
        self.assertFalse(out.success)
        self.assertIn("bad args", out.message)

    def test_register_rejects_non_callable(self):
        reg = ToolRegistry()
        with self.assertRaises(ValueError):
            reg.register("nope", 42)

    def test_register_rejects_empty_name(self):
        reg = ToolRegistry()
        with self.assertRaises(ValueError):
            reg.register("", lambda: ActionResult(True, ""))

    def test_known_tools_is_sorted(self):
        reg = ToolRegistry()
        reg.register("zeta", lambda: ActionResult(True, ""))
        reg.register("alpha", lambda: ActionResult(True, ""))
        self.assertEqual(reg.known_tools(), ["alpha", "zeta"])

    def test_stub_executor_records_calls(self):
        stub = StubExecutor(ActionResult(True, "stub"))
        stub.execute(tool_name="foo", tool_args={"k": 1})
        stub.execute(tool_name="bar", tool_args={})
        self.assertEqual(len(stub.calls), 2)
        self.assertEqual(stub.calls[0][0], "foo")
        self.assertEqual(stub.calls[1][0], "bar")


if __name__ == "__main__":
    unittest.main()