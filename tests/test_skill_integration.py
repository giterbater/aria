from __future__ import annotations

import time
import pytest
from aria_core.skills import SkillManager, SkillRegistry
from aria_core.skills.builtin import FileSkill, TerminalSkill, GitSkill
from aria_core.skills.builtin.doc_skill import DocSkill
from aria_core.skills.builtin.code_skill import CodeSkill


class TestParallelExecution:
    def test_execute_parallel(self, tmp_path):
        mgr = SkillManager()
        mgr.register(FileSkill(base_path=str(tmp_path)))

        # Create two files in parallel
        tasks = [
            ("file", {"action": "write", "path": "a.txt", "content": "file a"}),
            ("file", {"action": "write", "path": "b.txt", "content": "file b"}),
        ]
        results = mgr.execute_parallel(tasks)
        assert len(results) == 2
        assert all(r.success for r in results)
        assert (tmp_path / "a.txt").read_text() == "file a"
        assert (tmp_path / "b.txt").read_text() == "file b"

    def test_execute_batch(self, tmp_path):
        mgr = SkillManager()
        mgr.register(FileSkill(base_path=str(tmp_path)))
        results = mgr.execute_batch(
            ["file", "file"],
            shared_kwargs={"action": "write", "content": "batch"},
        )
        assert len(results) == 2

    def test_parallel_speedup(self, tmp_path):
        mgr = SkillManager()
        mgr.register(TerminalSkill())

        t0 = time.monotonic()
        mgr.execute_parallel([
            ("terminal", {"command": "python -c \"import time; time.sleep(0.1)\""}),
            ("terminal", {"command": "python -c \"import time; time.sleep(0.1)\""}),
            ("terminal", {"command": "python -c \"import time; time.sleep(0.1)\""}),
        ])
        sequential = time.monotonic() - t0
        # Parallel should be faster than 3 * 0.1s = 0.3s sequential
        # Allow generous margin for OS scheduling
        assert sequential < 0.5


class TestFullWorkflow:
    def test_file_write_read_cycle(self, tmp_path):
        mgr = SkillManager()
        mgr.register(FileSkill(base_path=str(tmp_path)))

        # Write
        r1 = mgr.execute_skill("file", action="write", path="data.txt", content="hello world")
        assert r1.success is True

        # Read
        r2 = mgr.execute_skill("file", action="read", path="data.txt")
        assert r2.success is True
        assert "hello world" in r2.output

        # Edit
        r3 = mgr.execute_skill("file", action="edit", path="data.txt", old_string="hello", new_string="goodbye")
        assert r3.success is True

        # Verify
        r4 = mgr.execute_skill("file", action="read", path="data.txt")
        assert "goodbye world" in r4.output

    def test_terminal_git_workflow(self, tmp_path):
        import subprocess
        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), capture_output=True)

        mgr = SkillManager()
        mgr.register(GitSkill(default_cwd=str(tmp_path)))
        mgr.register(FileSkill(base_path=str(tmp_path)))

        # Create file
        mgr.execute_skill("file", action="write", path="code.py", content="print('hello')")

        # Git status
        r1 = mgr.execute_skill("git", action="status")
        assert r1.success is True

        # Git add
        r2 = mgr.execute_skill("git", action="add", paths=["code.py"])
        assert r2.success is True

        # Git commit
        r3 = mgr.execute_skill("git", action="commit", message="add code")
        assert r3.success is True

        # Git log
        r4 = mgr.execute_skill("git", action="log")
        assert r4.success is True
        assert "add code" in r4.output

    def test_code_analysis_workflow(self):
        mgr = SkillManager()
        mgr.register(CodeSkill(base_path="."))

        # Scan
        r1 = mgr.execute_skill("code", action="scan", path="aria_core")
        assert r1.success is True
        assert r1.metadata["python_files"] > 0

        # Complexity
        r2 = mgr.execute_skill("code", action="complexity", path="aria_core")
        assert r2.success is True

        # Structure
        r3 = mgr.execute_skill("code", action="structure", path="aria_core")
        assert r3.success is True
        assert r3.metadata["modules"] > 0

    def test_doc_generation_workflow(self, tmp_path):
        mgr = SkillManager()
        mgr.register(DocSkill(base_path=str(tmp_path)))

        # Generate README
        r1 = mgr.execute_skill("documentation", action="generate_readme", project_name="MyProject", description="Test project")
        assert r1.success is True

        # Update changelog
        r2 = mgr.execute_skill("documentation", action="update_changelog", entry="v1.0.0 - Initial release")
        assert r2.success is True

        # List docs
        r3 = mgr.execute_skill("documentation", action="list_docs")
        assert r3.success is True
        assert r3.metadata["count"] >= 2


class TestSkillRegistryIntegration:
    def test_discover_all_builtins(self):
        mgr = SkillManager()
        mgr.register(FileSkill())
        mgr.register(TerminalSkill())
        mgr.register(GitSkill())
        mgr.register(DocSkill())
        mgr.register(CodeSkill())

        skills = mgr.registry.list_skills()
        names = {s.name for s in skills}
        assert "file" in names
        assert "terminal" in names
        assert "git" in names
        assert "documentation" in names
        assert "code" in names

    def test_find_by_tags(self):
        mgr = SkillManager()
        mgr.register(FileSkill())
        mgr.register(TerminalSkill())

        found = mgr.registry.find_by_tags(["file", "read"])
        assert len(found) >= 1

    def test_find_by_capability(self):
        mgr = SkillManager()
        mgr.register(FileSkill())
        mgr.register(TerminalSkill())

        found = mgr.registry.find_by_capability("execute shell commands")
        assert len(found) >= 1
