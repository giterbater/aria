from __future__ import annotations

import logging
from typing import List

from .task import Task, TaskState, TaskResult
from .runner import TaskRunner

logger = logging.getLogger("aria.autonomy.recovery")


class RecoveryManager:
    """Handles error recovery, retries, and task resumption.

    Provides strategies for recovering from failures:
    - Automatic retry with backoff
    - Skip failed steps
    - Resume from last checkpoint
    - Graceful degradation
    """

    def __init__(self, runner: TaskRunner):
        self._runner = runner

    def recover_failed_tasks(self) -> list[dict]:
        """Find and attempt to recover all failed tasks."""
        store = self._runner._store
        tasks = store.load_all_tasks()
        results = []

        for task in tasks:
            if task.state == TaskState.FAILED and task.can_retry:
                logger.info("Recovering task %s (retry %d/%d)", task.id, task.retry_count + 1, task.max_retries)
                result = self._runner.retry_task(task)
                results.append({
                    "task_id": task.id,
                    "task_name": task.name,
                    "retry": task.retry_count,
                    "success": result.success,
                    "error": result.error,
                })
            elif task.state == TaskState.RUNNING:
                logger.info("Resuming interrupted task %s", task.id)
                result = self._runner.run_task(task)
                results.append({
                    "task_id": task.id,
                    "task_name": task.name,
                    "action": "resumed",
                    "success": result.success,
                })

        return results

    def skip_failed_step(self, task: Task) -> TaskResult:
        """Skip the current failed step and continue."""
        if task.state != TaskState.FAILED:
            return TaskResult(success=False, error="Task is not in failed state")

        task.current_step += 1
        task.state = TaskState.RUNNING
        task.last_error = ""
        task.updated_at = __import__("datetime").datetime.now()
        self._runner._store.save_task(task)

        logger.info("Skipped step %d in task %s", task.current_step - 1, task.id)
        return self._runner.run_task(task)

    def get_recovery_suggestions(self, task: Task) -> list[str]:
        """Analyze a failed task and suggest recovery strategies."""
        suggestions = []

        if task.can_retry:
            suggestions.append(f"Retry task (attempt {task.retry_count + 1}/{task.max_retries})")

        if task.current_step > 0:
            suggestions.append(f"Skip step {task.current_step} and continue from step {task.current_step + 1}")

        if task.last_error:
            if "timeout" in task.last_error.lower():
                suggestions.append("Increase timeout for slow operations")
            elif "permission" in task.last_error.lower():
                suggestions.append("Check file/directory permissions")
            elif "not found" in task.last_error.lower():
                suggestions.append("Verify required files exist")
            elif "connection" in task.last_error.lower():
                suggestions.append("Check network connectivity")

        if len(task.steps) > 1:
            suggestions.append("Split task into smaller subtasks")

        return suggestions

    def summarize_recovery_status(self) -> str:
        """Summarize the recovery status across all tasks."""
        store = self._runner._store
        tasks = store.load_all_tasks()

        total = len(tasks)
        completed = sum(1 for t in tasks if t.state == TaskState.COMPLETED)
        failed = sum(1 for t in tasks if t.state == TaskState.FAILED)
        running = sum(1 for t in tasks if t.state == TaskState.RUNNING)
        retryable = sum(1 for t in tasks if t.can_retry)

        lines = [
            f"Tasks: {total} total",
            f"  Completed: {completed}",
            f"  Failed: {failed}",
            f"  Running: {running}",
            f"  Retryable: {retryable}",
        ]

        if retryable > 0:
            lines.append(f"  Run recover_failed_tasks() to retry {retryable} task(s)")

        return "\n".join(lines)
