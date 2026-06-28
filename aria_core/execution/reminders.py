# aria_core/execution/reminders.py
"""
In-memory pending-reminder singleton.

The four tools (``set_reminder`` / ``cancel_reminder`` / ``current_time``
/ ``launch_application``) live in :mod:`aria_core.execution.registry`.
This module only owns the storage backing ``set_reminder`` /
``cancel_reminder`` so the worker can poll for fired timers each turn.

Design notes
------------
* All mutation is guarded by a ``threading.Lock`` because reminders can
  be set by the worker thread and read by a separate timer thread.
* :meth:`PendingReminders.tick` is a test seam – it fires every timer
  whose deadline has passed instead of waiting for ``threading.Timer``
  to wake up.  Production code should use :meth:`drain_fired` instead.
* Fired reminders are kept until :meth:`acknowledge_fired` is called so
  the worker can present them exactly once.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class PendingReminder:
    """A reminder that has fired and is awaiting acknowledgement."""
    reminder_id: str
    message: str
    fired_at: float  # epoch seconds


class PendingReminders:
    """Process-singleton buffer of fired reminders."""

    _instance: Optional["PendingReminders"] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Each entry: (deadline_epoch, reminder_id, message)
        self._pending: List[tuple[float, str, str]] = []
        self._fired: List[PendingReminder] = []

    # ------------------------------------------------------------------
    # Singleton accessor
    # ------------------------------------------------------------------
    @classmethod
    def instance(cls) -> "PendingReminders":
        """Return the process-wide singleton, creating it on first use."""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Drop the singleton and start a fresh one.

        Intended for tests; production code never calls this.
        """
        with cls._instance_lock:
            cls._instance = None

    # ------------------------------------------------------------------
    # Mutation API (used by the tools)
    # ------------------------------------------------------------------
    def schedule(self, reminder_id: str, message: str, seconds: int) -> None:
        """Schedule *message* to fire *seconds* from now."""
        deadline = time.time() + max(0, int(seconds))
        with self._lock:
            self._pending.append((deadline, reminder_id, message))

    def cancel_by_message(self, substring: str) -> int:
        """Cancel every pending timer whose message contains *substring*.

        Returns the number of cancellations.
        """
        sub = substring.lower()
        with self._lock:
            remaining: List[tuple[float, str, str]] = []
            cancelled = 0
            for entry in self._pending:
                _, _, msg = entry
                if sub in msg.lower():
                    cancelled += 1
                else:
                    remaining.append(entry)
            self._pending = remaining
            return cancelled

    # ------------------------------------------------------------------
    # Drain API (used by the worker)
    # ------------------------------------------------------------------
    def drain_fired(self) -> List[PendingReminder]:
        """Move every due reminder from ``pending`` to ``fired`` and
        return a snapshot of ``fired``.

        Safe to call repeatedly; each reminder is delivered exactly once.
        """
        now = time.time()
        with self._lock:
            still_pending: List[tuple[float, str, str]] = []
            for entry in self._pending:
                deadline, rid, msg = entry
                if deadline <= now:
                    self._fired.append(
                        PendingReminder(
                            reminder_id=rid, message=msg, fired_at=now
                        )
                    )
                else:
                    still_pending.append(entry)
            self._pending = still_pending
            return list(self._fired)

    def acknowledge_fired(self, reminder_id: str) -> bool:
        """Remove a fired reminder once the worker has handled it."""
        with self._lock:
            for i, entry in enumerate(self._fired):
                if entry.reminder_id == reminder_id:
                    del self._fired[i]
                    return True
            return False

    # ------------------------------------------------------------------
    # Test seam – fast-forward timers
    # ------------------------------------------------------------------
    def tick(self, now: Optional[float] = None) -> List[PendingReminder]:
        """Force every pending timer whose deadline <= *now* to fire.

        ``now`` defaults to ``time.time()``; tests usually pass a fixed
        timestamp to avoid relying on real wall-clock time.
        """
        moment = now if now is not None else time.time()
        with self._lock:
            still_pending: List[tuple[float, str, str]] = []
            for entry in self._pending:
                deadline, rid, msg = entry
                if deadline <= moment:
                    self._fired.append(
                        PendingReminder(
                            reminder_id=rid, message=msg, fired_at=moment
                        )
                    )
                else:
                    still_pending.append(entry)
            self._pending = still_pending
            return list(self._fired)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    def fired_count(self) -> int:
        with self._lock:
            return len(self._fired)