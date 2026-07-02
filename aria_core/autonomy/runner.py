from __future__ import annotations

import datetime
import logging
import time
from typing import Any, Callable

from .task import Task, TaskState, TaskResult
from .checkpoint import CheckpointStore

logger = logging.getLogger("aria.autonomy.runner")


class TaskRunner:
    """Executes long-running tasks with checkpointing and error recovery.

    Manages task lifecycle: create → run → checkpoint → complete/fail/retry.
    """

    def __init__(self, checkpoint_store: CheckpointStore | None = None):
        self._store = checkpoint_store or CheckpointStore()
        self._handlers: dict[str, Callable] = {}
        self._on_progress: Callable | None = None

    def register_handler(self, step_type: str, handler: Callable) -> None:
        """Register a handler for a step type."""
        self._handlers[step_type] = handler

    def set_progress_callback(self, callback: Callable) -> None:
        """Set a callback for progress updates."""
        self._on_progress = callback

    def create_task(
        self,
        name: str,
        steps: list[dict],
        description: str = "",
        priority: float = 1.0,
        tags: list[str] | None = None,
    ) -> Task:
        task = Task(
            name=name,
            description=description,
            steps=steps,
            priority=priority,
            tags=tags or [],
        )
        self._store.save_task(task)
        logger.info("Created task %s: %s (%d steps)", task.id, name, len(steps))
        return task

    def run_task(self, task: Task) -> TaskResult:
        """Execute a task from its current step to completion."""
        if task.state == TaskState.COMPLETED:
            return task.result or TaskResult(ok=True, output="already completed")

        task.state = TaskState.RUNNING
        task.started_at = task.started_at or datetime.datetime.now()
        task.updated_at = datetime.datetime.now()
        self._store.save_task(task)

        while task.current_step < len(task.steps):
            step = task.steps[task.current_step]
            step_type = step.get("type", "unknown")
            handler = self._handlers.get(step_type)

            if handler is None:
                logger.warning("No handler for step type: %s", step_type)
                task.current_step += 1
                continue

            try:
                t0 = time.monotonic()
                result = handler(**step.get("args", {}))
                elapsed = (time.monotonic() - t0) * 1000

                if not result.success:
                    task.last_error = result.error or "step failed"
                    task.state = TaskState.FAILED
                    task.result = result
                    task.updated_at = datetime.datetime.now()
                    self._store.save_task(task)
                    self._store.save_checkpoint(
                        task.id, task.current_step, "failed",
                        {"error": task.last_error, "elapsed_ms": elapsed},
                    )
                    logger.warning("Task %s failed at step %d: %s", task.id, task.current_step, task.last_error)
                    return result

                task.current_step += 1
                task.updated_at = datetime.datetime.now()
                self._store.save_task(task)
                self._store.save_checkpoint(
                    task.id, task.current_step, "completed",
                    {"elapsed_ms": elapsed, "output": str(result.output)[:200]},
                )

                if self._on_progress:
                    self._on_progress(task, task.current_step, len(task.steps))

            except Exception as exc:
                task.last_error = str(exc)
                task.state = TaskState.FAILED
                task.result = TaskResult(success=False, error=str(exc))
                task.updated_at = datetime.datetime.now()
                self._store.save_task(task)
                self._store.save_checkpoint(
                    task.id, task.current_step, "error",
                    {"error": str(exc)},
                )
                logger.exception("Task %s raised at step %d", task.id, task.current_step)
                return task.result

        task.state = TaskState.COMPLETED
        task.completed_at = datetime.datetime.now()
        task.updated_at = datetime.datetime.now()
        task.result = TaskResult(success=True, output=f"Completed {len(task.steps)} steps")
        self._store.save_task(task)
        logger.info("Task %s completed", task.id)
        return task.result

    def retry_task(self, task: Task) -> TaskResult:
        """Retry a failed task from its last checkpoint."""
        if not task.can_retry:
            return TaskResult(
                success=False,
                error=f"Cannot retry: state={task.state.value}, retries={task.retry_count}/{task.max_retries}",
            )

        task.retry_count += 1
        task.state = TaskState.RUNNING
        task.updated_at = datetime.datetime.now()
        self._store.save_task(task)
        logger.info("Retrying task %s (attempt %d/%d)", task.id, task.retry_count, task.max_retries)

        return self.run_task(task)

    def pause_task(self, task: Task) -> None:
        task.state = TaskState.PAUSED
        task.updated_at = datetime.datetime.now()
        self._store.save_task(task)
        logger.info("Paused task %s at step %d", task.id, task.current_step)

    def cancel_task(self, task: Task) -> None:
        task.state = TaskState.CANCELLED
        task.completed_at = datetime.datetime.now()
        task.updated_at = datetime.datetime.now()
        self._store.save_task(task)
        logger.info("Cancelled task %s", task.id)

    def resume_task(self, task: Task) -> TaskResult:
        """Resume a paused task."""
        if task.state != TaskState.PAUSED:
            return TaskResult(success=False, error=f"Task is {task.state.value}, not paused")
        task.state = TaskState.RUNNING
        task.updated_at = datetime.datetime.now()
        self._store.save_task(task)
        return self.run_task(task)

    def get_resumable_tasks(self) -> list[Task]:
        return self._store.load_resumable_tasks()

    def get_task(self, task_id: str) -> Task | None:
        return self._store.load_task(task_id)
