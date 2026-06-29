from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from .state import CycleState

logger = logging.getLogger("aria.cto.loop")


def _run_async(coro) -> Any:
    """Run an async coroutine from sync code. Creates a new loop if needed."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()

    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def _llm_generate(llm, prompt: str, max_tokens: int = 1024, temperature: float = 0.3) -> str:
    """Call LLM, preferring sync path to avoid event loop issues."""
    if hasattr(llm, "generate_sync"):
        return llm.generate_sync(prompt, max_tokens=max_tokens, temperature=temperature)
    return _run_async(llm.generate(prompt, max_tokens=max_tokens, temperature=temperature))


class CTOLoop:
    """The 7-phase autonomous cycle: inspect -> choose -> execute -> test -> review -> commit -> remember."""

    def __init__(self, brain: Any) -> None:
        self._brain = brain
        self._running = False

    def run_single_cycle(self) -> CycleState:
        state = CycleState()
        try:
            state = self._phase_inspect(state)
            state = self._phase_choose(state)
            if state.error:
                return state
            state = self._phase_execute(state)
            state = self._phase_test(state)
            state = self._phase_review(state)
            state = self._phase_commit(state)
            state = self._phase_remember(state)
        except Exception as exc:
            logger.exception("Cycle %s failed", state.cycle_id)
            state = state.set_error(str(exc))
        return state

    def run_continuous(self, interval_seconds: int = 30, max_cycles: int | None = None) -> None:
        import time
        self._running = True
        cycle_count = 0
        logger.info("Starting continuous CTO loop (interval=%ds)", interval_seconds)

        while self._running:
            if max_cycles and cycle_count >= max_cycles:
                logger.info("Reached max cycles (%d), stopping", max_cycles)
                break
            state = self.run_single_cycle()
            cycle_count += 1
            logger.info(
                "Cycle %s completed (phase=%s, actions=%d, files=%d, error=%s)",
                state.cycle_id, state.phase, len(state.actions_taken),
                len(state.files_modified), state.error,
            )
            if not self._running:
                break
            time.sleep(interval_seconds)

        logger.info("CTO loop stopped after %d cycles", cycle_count)

    def stop(self) -> None:
        self._running = False

    # ------------------------------------------------------------------
    # Phase implementations
    # ------------------------------------------------------------------

    def _phase_inspect(self, state: CycleState) -> CycleState:
        state = state.set_phase("inspect")
        logger.debug("Phase: inspect")

        repo_path = self._brain.config.repo_path

        git_status = self._brain.cached(
            "git_status",
            lambda: self._brain.git.status(repo_path),
            ttl=5.0,
        )
        structure = self._brain.cached(
            "structure",
            lambda: self._brain.tools.dispatch("get_structure", {"path": repo_path, "max_depth": 3}),
            ttl=60.0,
        )
        file_list = self._brain.cached(
            "file_list",
            lambda: self._brain.tools.dispatch("list_files", {"path": repo_path, "recursive": True, "pattern": "*.py"}),
            ttl=60.0,
        )
        recent_decisions = self._brain.project_memory.get_recent_decisions(limit=5)

        todos = self._brain.cached(
            "todos",
            lambda: self._brain.tools.dispatch("search_code", {
                "pattern": "TODO|FIXME|HACK|XXX|BUG",
                "path": repo_path,
                "include": "*.py",
                "max_results": 10,
            }),
            ttl=120.0,
        )

        last_actions = []
        for d in recent_decisions[:3]:
            for a in d.get("value", {}).get("actions", []):
                tool = a.get("tool", "?")
                args = a.get("args", {})
                if tool == "read_file":
                    last_actions.append(f"read_file({args.get('path', '?')})")
                else:
                    last_actions.append(tool)

        context = {
            "git_status": git_status.output,
            "project_structure": structure.output,
            "python_files": file_list.output if file_list.success else "(none)",
            "recent_decisions": [
                {"action": d.get("key"), "outcome": d.get("value", {}).get("outcome", "unknown")}
                for d in recent_decisions
            ],
            "todos_found": todos.output if todos.success else "(none)",
            "last_actions_done": ", ".join(last_actions) if last_actions else "(none)",
        }
        self._brain.context = context
        return state

    def _phase_choose(self, state: CycleState) -> CycleState:
        state = state.set_phase("choose")
        logger.debug("Phase: choose")

        if self._brain.llm is None:
            state = state.set_error("No LLM configured")
            return state

        prompt = self._brain.build_choose_prompt()
        raw = _llm_generate(self._brain.llm, prompt)

        action = self._parse_llm_action(raw)
        tool_name = action.get("action", "")
        known = self._brain.tools.known_tools()

        if tool_name and tool_name not in known:
            logger.warning("LLM chose unknown tool '%s'", tool_name)
            action = {
                "action": "read_file",
                "args": {"path": self._brain.config.repo_path + "/cto/brain.py"},
                "reasoning": f"LLM suggested '{tool_name}' which is not available.",
            }

        if tool_name == "read_file":
            target = action.get("args", {}).get("path", "")
            recent_files = set()
            for d in self._brain.project_memory.get_recent_decisions(limit=3):
                for a in d.get("value", {}).get("actions", []):
                    if a.get("tool") == "read_file":
                        recent_files.add(a.get("args", {}).get("path", ""))

            if target in recent_files:
                files_result = self._brain.tools.dispatch("list_files", {
                    "path": self._brain.config.repo_path,
                    "recursive": True,
                    "pattern": "*.py",
                })
                if files_result.success:
                    all_files = [
                        f for f in files_result.output.splitlines()
                        if f.endswith(".py") and f not in recent_files
                    ]
                    if all_files:
                        import random
                        pick = random.choice(all_files[:20])
                        action = {
                            "action": "read_file",
                            "args": {"path": pick},
                            "reasoning": f"Switching to {pick} — already read the previous file.",
                        }

        self._brain.current_action = action
        logger.info("Chose action: %s", json.dumps(action, indent=2))
        return state

    def _phase_execute(self, state: CycleState) -> CycleState:
        state = state.set_phase("execute")
        logger.debug("Phase: execute")

        action = self._brain.current_action
        if not action:
            return state

        specialist = action.get("specialist_needed")
        if specialist:
            return self._execute_delegation(state, action)

        tool_name = action.get("action", "")
        tool_args = action.get("args", {})

        if not tool_name:
            return state

        if self._brain.permissions.is_blocked(tool_name, tool_args):
            logger.warning("Tool %s is blocked by permissions", tool_name)
            state = state.record_action({
                "tool": tool_name, "status": "blocked", "reason": "permission denied",
            })
            return state

        result = self._brain.tools.dispatch(tool_name, tool_args)
        action_record = {
            "tool": tool_name, "args": tool_args,
            "success": result.success, "output_preview": result.output[:500],
        }
        state = state.record_action(action_record)

        if result.success and tool_name in ("apply_edit", "create_file", "delete_file"):
            path = tool_args.get("path", "")
            if path:
                state = state.set_files_modified(state.files_modified + [path])

        logger.info("Executed %s: success=%s", tool_name, result.success)
        return state

    def _execute_delegation(self, state: CycleState, action: dict) -> CycleState:
        specialist = action.get("specialist_needed", "mimo")
        task_desc = action.get("task_description", action.get("reasoning", "No description"))

        from delegation.interfaces import SpecialistRequest
        request = SpecialistRequest(
            specialist_name=specialist,
            task_description=task_desc,
            context_files=list(self._brain.context.get("modified_files", {}).keys()),
            file_contents=self._brain.context.get("modified_files", {}),
        )

        response = self._brain.specialist_manager.delegate(request)
        state = state.record_action({
            "tool": "delegate", "specialist": specialist,
            "status": response.status, "summary": response.summary,
        })

        if response.status == "success" and response.files_modified:
            state = state.set_files_modified(response.files_modified)

        return state

    def _phase_test(self, state: CycleState) -> CycleState:
        state = state.set_phase("test")
        logger.debug("Phase: test")

        action_was_run_tests = any(
            a.get("tool") == "run_tests" for a in state.actions_taken
        )

        if not state.files_modified and not action_was_run_tests:
            state = state.set_tests_result(True)
            return state

        result = self._brain.tools.dispatch("run_tests", {
            "cwd": self._brain.config.repo_path,
        })
        passed = result.success
        state = state.set_tests_result(passed)

        if not passed:
            self._brain.test_failures = result.output
            logger.warning("Tests failed:\n%s", result.output[:500])
        else:
            self._brain.test_failures = None
            logger.info("Tests passed")

        return state

    def _phase_review(self, state: CycleState) -> CycleState:
        state = state.set_phase("review")
        logger.debug("Phase: review")

        if not state.files_modified:
            state = state.set_review(True)
            return state

        if self._brain.llm is None:
            state = state.set_review(True)
            return state

        diff_result = self._brain.git.diff(self._brain.config.repo_path)
        prompt = self._brain.build_review_prompt(diff_result.output)

        raw = _llm_generate(self._brain.llm, prompt)

        review = self._parse_llm_review(raw)
        approved = review.get("approved", True)
        state = state.set_review(approved)

        if not approved:
            issues = review.get("issues", [])
            logger.warning("Review rejected: %s", issues)
            if state.actions_taken and self._brain.test_failures:
                for attempt in range(self._brain.config.max_review_retries):
                    logger.info("Retry attempt %d", attempt + 1)
                    fix_action = self._analyze_failure()
                    if fix_action:
                        self._brain.current_action = fix_action
                        state = self._phase_execute(state)
                        state = self._phase_test(state)
                        if state.tests_passed:
                            break
        else:
            logger.info("Review approved")

        return state

    def _phase_commit(self, state: CycleState) -> CycleState:
        state = state.set_phase("commit")
        logger.debug("Phase: commit")

        if not state.files_modified:
            return state

        if self._brain.llm is None:
            message = f"CTO cycle {state.cycle_id}: modified {len(state.files_modified)} file(s)"
        else:
            message = self._generate_commit_message(state)

        status_result = self._brain.git.status(self._brain.config.repo_path)
        if "(clean working tree)" in status_result.output:
            return state

        self._brain.git.add(self._brain.config.repo_path, state.files_modified)
        commit_result = self._brain.git.commit(self._brain.config.repo_path, message)

        if commit_result.success:
            state = state.set_commit("committed")
            logger.info("Committed: %s", message[:100])
        else:
            logger.warning("Commit failed: %s", commit_result.output)

        return state

    def _phase_remember(self, state: CycleState) -> CycleState:
        state = state.set_phase("remember")
        logger.debug("Phase: remember")

        decision = {
            "cycle_id": state.cycle_id,
            "actions": state.actions_taken,
            "files_modified": state.files_modified,
            "tests_passed": state.tests_passed,
            "review_approved": state.review_approved,
            "commit_sha": state.commit_sha,
            "error": state.error,
            "outcome": "success" if not state.error and state.tests_passed else "failed",
        }
        self._brain.project_memory.store_decision(decision)

        if state.files_modified:
            for f in state.files_modified:
                self._brain.project_memory.store_codebase_fact(f"modified:{f}", state.cycle_id)

        return state

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_llm_action(self, raw: str) -> dict:
        try:
            text = raw.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text)
        except (json.JSONDecodeError, IndexError):
            logger.warning("Failed to parse LLM action")
            return {"action": "", "args": {}, "reasoning": "parse failure"}

    def _parse_llm_review(self, raw: str) -> dict:
        try:
            text = raw.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text)
        except (json.JSONDecodeError, IndexError):
            return {"approved": True, "summary": "review parse failure"}

    def _generate_commit_message(self, state: CycleState) -> str:
        files = ", ".join(state.files_modified[:5])
        actions = [a.get("tool", "unknown") for a in state.actions_taken]
        return f"CTO: {', '.join(actions)} on {files}"

    def _analyze_failure(self) -> dict | None:
        if not self._brain.test_failures:
            return None
        return {"action": "run_tests", "args": {"cwd": self._brain.config.repo_path}}
