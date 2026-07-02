from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from aria_core.autonomy import Task, TaskState, TaskResult, TaskRunner, CheckpointStore, RecoveryManager


class TestTask:
    def test_defaults(self):
        t = Task(name="test")
        assert t.state == TaskState.PENDING
        assert t.progress == 0.0
        assert t.is_terminal is False

    def test_progress_with_steps(self):
        t = Task(name="test", steps=[{"type": "a"}, {"type": "b"}, {"type": "c"}])
        t.current_step = 1
        assert t.progress == pytest.approx(1 / 3)

    def test_progress_complete(self):
        t = Task(name="test", state=TaskState.COMPLETED, steps=[{"type": "a"}])
        assert t.progress == 1.0

    def test_can_retry(self):
        t = Task(name="test", state=TaskState.FAILED, retry_count=0, max_retries=3)
        assert t.can_retry is True

    def test_cannot_retry_max(self):
        t = Task(name="test", state=TaskState.FAILED, retry_count=3, max_retries=3)
        assert t.can_retry is False

    def test_cannot_retry_running(self):
        t = Task(name="test", state=TaskState.RUNNING, retry_count=0, max_retries=3)
        assert t.can_retry is False


class TestCheckpointStore:
    def test_save_and_load(self, tmp_path):
        store = CheckpointStore(str(tmp_path / "test.db"))
        t = Task(name="test task", steps=[{"type": "a"}])
        store.save_task(t)
        loaded = store.load_task(t.id)
        store.close()
        assert loaded is not None
        assert loaded.name == "test task"
        assert loaded.steps == [{"type": "a"}]

    def test_load_resumable(self, tmp_path):
        store = CheckpointStore(str(tmp_path / "test.db"))
        t1 = Task(name="running", state=TaskState.RUNNING)
        t2 = Task(name="completed", state=TaskState.COMPLETED)
        t3 = Task(name="pending", state=TaskState.PENDING)
        store.save_task(t1)
        store.save_task(t2)
        store.save_task(t3)
        resumable = store.load_resumable_tasks()
        store.close()
        assert len(resumable) == 2
        names = {t.name for t in resumable}
        assert "running" in names
        assert "pending" in names

    def test_checkpoint(self, tmp_path):
        store = CheckpointStore(str(tmp_path / "test.db"))
        t = Task(name="test")
        store.save_task(t)
        store.save_checkpoint(t.id, 0, "completed", {"elapsed_ms": 100})
        store.save_checkpoint(t.id, 1, "completed", {"elapsed_ms": 200})
        checkpoints = store.get_checkpoints(t.id)
        store.close()
        assert len(checkpoints) == 2
        assert checkpoints[0]["step_index"] == 0
        assert checkpoints[1]["step_index"] == 1

    def test_last_checkpoint(self, tmp_path):
        store = CheckpointStore(str(tmp_path / "test.db"))
        t = Task(name="test")
        store.save_task(t)
        store.save_checkpoint(t.id, 0, "completed", {"elapsed_ms": 100})
        store.save_checkpoint(t.id, 1, "failed", {"error": "boom"})
        last = store.get_last_checkpoint(t.id)
        store.close()
        assert last is not None
        assert last["step_index"] == 1
        assert last["state"] == "failed"

    def test_delete_task(self, tmp_path):
        store = CheckpointStore(str(tmp_path / "test.db"))
        t = Task(name="test")
        store.save_task(t)
        store.save_checkpoint(t.id, 0, "completed", {})
        store.delete_task(t.id)
        assert store.load_task(t.id) is None
        assert store.get_checkpoints(t.id) == []
        store.close()

    def test_persistence(self, tmp_path):
        db = tmp_path / "test.db"
        s1 = CheckpointStore(str(db))
        t = Task(name="persistent")
        s1.save_task(t)
        s1.close()
        s2 = CheckpointStore(str(db))
        loaded = s2.load_task(t.id)
        s2.close()
        assert loaded is not None
        assert loaded.name == "persistent"


class TestTaskRunner:
    def test_create_and_run(self, tmp_path):
        runner = TaskRunner(CheckpointStore(str(tmp_path / "test.db")))
        handler = MagicMock(return_value=TaskResult(success=True, output="ok"))
        runner.register_handler("step_a", handler)

        task = runner.create_task("test", [{"type": "step_a", "args": {"x": 1}}])
        result = runner.run_task(task)
        assert result.success is True
        assert task.state == TaskState.COMPLETED
        assert task.current_step == 1

    def test_step_failure(self, tmp_path):
        runner = TaskRunner(CheckpointStore(str(tmp_path / "test.db")))
        handler = MagicMock(return_value=TaskResult(success=False, error="failed"))
        runner.register_handler("step_a", handler)

        task = runner.create_task("test", [{"type": "step_a"}])
        result = runner.run_task(task)
        assert result.success is False
        assert task.state == TaskState.FAILED

    def test_retry(self, tmp_path):
        runner = TaskRunner(CheckpointStore(str(tmp_path / "test.db")))
        call_count = 0

        def flaky_handler(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return TaskResult(success=False, error="first fail")
            return TaskResult(success=True, output="ok")

        runner.register_handler("step_a", flaky_handler)
        task = runner.create_task("test", [{"type": "step_a"}])
        runner.run_task(task)
        assert task.state == TaskState.FAILED

        result = runner.retry_task(task)
        assert result.success is True
        assert task.state == TaskState.COMPLETED
        assert task.retry_count == 1

    def test_pause_and_resume(self, tmp_path):
        runner = TaskRunner(CheckpointStore(str(tmp_path / "test.db")))
        handler = MagicMock(return_value=TaskResult(success=True))
        runner.register_handler("step_a", handler)

        task = runner.create_task("test", [{"type": "step_a"}, {"type": "step_a"}])
        task.current_step = 1
        task.state = TaskState.RUNNING
        runner._store.save_task(task)

        runner.pause_task(task)
        assert task.state == TaskState.PAUSED

        result = runner.resume_task(task)
        assert result.success is True
        assert task.state == TaskState.COMPLETED

    def test_cancel(self, tmp_path):
        runner = TaskRunner(CheckpointStore(str(tmp_path / "test.db")))
        task = runner.create_task("test", [{"type": "step_a"}])
        runner.cancel_task(task)
        assert task.state == TaskState.CANCELLED

    def test_progress_callback(self, tmp_path):
        runner = TaskRunner(CheckpointStore(str(tmp_path / "test.db")))
        handler = MagicMock(return_value=TaskResult(success=True))
        runner.register_handler("step_a", handler)

        progress_calls = []
        runner.set_progress_callback(lambda t, step, total: progress_calls.append((step, total)))

        task = runner.create_task("test", [{"type": "step_a"}, {"type": "step_a"}])
        runner.run_task(task)
        assert len(progress_calls) == 2

    def test_no_handler(self, tmp_path):
        runner = TaskRunner(CheckpointStore(str(tmp_path / "test.db")))
        task = runner.create_task("test", [{"type": "unknown"}])
        result = runner.run_task(task)
        # Skips unknown steps, completes
        assert task.state == TaskState.COMPLETED


class TestRecoveryManager:
    def test_recover_failed(self, tmp_path):
        runner = TaskRunner(CheckpointStore(str(tmp_path / "test.db")))
        handler = MagicMock(return_value=TaskResult(success=False, error="fail"))
        runner.register_handler("step_a", handler)
        recovery = RecoveryManager(runner)

        task = runner.create_task("test", [{"type": "step_a"}])
        runner.run_task(task)
        assert task.state == TaskState.FAILED

        results = recovery.recover_failed_tasks()
        assert len(results) == 1
        assert results[0]["retry"] == 1

    def test_skip_step(self, tmp_path):
        runner = TaskRunner(CheckpointStore(str(tmp_path / "test.db")))
        handler = MagicMock(return_value=TaskResult(success=True))
        runner.register_handler("step_a", handler)

        task = runner.create_task("test", [{"type": "step_a"}, {"type": "step_a"}])
        task.state = TaskState.FAILED
        task.current_step = 0
        runner._store.save_task(task)

        recovery = RecoveryManager(runner)
        result = recovery.skip_failed_step(task)
        # Handler runs and completes remaining steps
        assert task.current_step == 2

    def test_recovery_suggestions(self, tmp_path):
        runner = TaskRunner(CheckpointStore(str(tmp_path / "test.db")))
        recovery = RecoveryManager(runner)

        task = Task(name="test", state=TaskState.FAILED, retry_count=0, max_retries=3,
                     last_error="connection timeout", current_step=2,
                     steps=[{}, {}, {}])
        suggestions = recovery.get_recovery_suggestions(task)
        assert len(suggestions) > 0
        assert any("timeout" in s.lower() for s in suggestions)

    def test_summarize_status(self, tmp_path):
        runner = TaskRunner(CheckpointStore(str(tmp_path / "test.db")))
        recovery = RecoveryManager(runner)
        runner.create_task("a", [{"type": "x"}])
        runner.create_task("b", [{"type": "x"}])
        summary = recovery.summarize_recovery_status()
        assert "Tasks:" in summary
        assert "2 total" in summary
