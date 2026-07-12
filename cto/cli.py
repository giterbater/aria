from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time
from pathlib import Path

from .config import CTOConfig

logger = logging.getLogger("aria.cto.cli")


def _validate_environment(config: CTOConfig) -> list[str]:
    """Validate the environment and return list of issues (empty = all good)."""
    issues = []

    repo = config.repo_path_resolved()
    if not repo.is_dir():
        issues.append(f"Repository not found: {repo}")
    elif not (repo / ".git").exists():
        issues.append(f"Not a git repository: {repo}")

    try:
        result = __import__("subprocess").run(
            ["git", "--version"], capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            issues.append("git not available")
    except FileNotFoundError:
        issues.append("git not installed")

    python_ok = False
    found_py = None
    candidates = [sys.executable, "python", "python3"]
    import glob as _glob
    for pattern in [
        r"C:\Users\*\AppData\Local\Programs\Python\Python3*\python.exe",
        r"C:\Python3*\python.exe",
    ]:
        candidates.extend(_glob.glob(pattern))
    for py in candidates:
        try:
            result = __import__("subprocess").run(
                [py, "-c", "import pytest; print(pytest.__version__)"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                python_ok = True
                found_py = py
                break
        except (FileNotFoundError, __import__("subprocess").TimeoutExpired):
            continue
    if not python_ok:
        issues.append("pytest not available — run: pip install pytest")
    else:
        logger.info("Found pytest via: %s", found_py)

    provider = config.provider.lower()
    if provider == "nvidia":
        api_key = config.resolve_api_key()
        if not api_key:
            issues.append(
                "NVIDIA API key not found. Set NVIDIA_API_KEY environment variable "
                "or pass --api-key."
            )
    elif provider == "ollama":
        try:
            import httpx
            ollama_url = config.base_url or config.ollama_base_url
            resp = httpx.get(f"{ollama_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = [m.get("name", "") for m in resp.json().get("models", [])]
                if not any(config.model in m for m in models):
                    issues.append(
                        f"Model '{config.model}' not found in Ollama. "
                        f"Available: {', '.join(models[:5]) or '(none)'}. "
                        f"Run: ollama pull {config.model}"
                    )
            else:
                issues.append(f"Ollama responded with status {resp.status_code}")
        except Exception:
            issues.append(f"Cannot reach Ollama at {config.ollama_base_url} — is it running?")

    return issues


def _create_prompt_session():
    """Create a prompt_toolkit session with multi-line support.

    - Enter submits when cursor is at end of a non-empty line
    - Alt+Enter inserts a newline (for multi-line input)
    - Pasted multi-line text is treated as one message
    """
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.key_binding import KeyBindings

    bindings = KeyBindings()

    @bindings.add("enter")
    def _(event):
        buf = event.app.current_buffer
        text = buf.text
        cursor_at_end = buf.cursor_position == len(text)

        if not text:
            buf.validate_and_handle()
        elif cursor_at_end:
            buf.validate_and_handle()
        else:
            buf.insert_text("\n")

    @bindings.add("escape", "enter")
    def _(event):
        event.app.current_buffer.insert_text("\n")

    return PromptSession(
        key_bindings=bindings,
        history=InMemoryHistory(),
        multiline=False,
        wrap_lines=True,
    )


def _interactive_mode(brain) -> None:
    session = _create_prompt_session()

    print("\n=== ARIA CTO Interactive Mode ===")
    print("Enter to submit. Alt+Enter for new line. Type 'quit' to exit.\n")

    conversation: list[dict[str, str]] = []

    while True:
        try:
            user_input = session.prompt("You> ")
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        user_input = user_input.strip()
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye.")
            break

        if brain.llm is None:
            print("[Error] No LLM available. Cannot process requests.")
            continue

        print(f"\n[CTO] Processing: {user_input[:100]}{'...' if len(user_input) > 100 else ''}")

        conversation.append({"role": "user", "content": user_input})

        tool_names = ", ".join(brain.tools.known_tools())
        history_text = ""
        if len(conversation) > 1:
            recent = conversation[-8:]
            history_text = "\n".join(
                f"{'User' if m['role'] == 'user' else 'CTO'}: {m['content'][:300]}"
                for m in recent[:-1]
            )
            history_text = f"\n\nConversation so far:\n{history_text}\n"

        prompt = (
            f"You are ARIA, an autonomous CTO. "
            f"EXACT TOOL NAMES: {tool_names}\n"
            f"{history_text}\n"
            f"Current request:\n{user_input}\n\n"
            f"Use a tool. Respond with JSON:\n"
            f'{{"action": "<tool_name>", "args": {{"path": "..."}}, "reasoning": "..."}}\n'
            f"Example: {json.dumps({'action': 'read_file', 'args': {'path': 'main.py'}, 'reasoning': 'reading file'})}"
        )

        try:
            resp = brain.generate(prompt)
            if not resp.success:
                print(f"[Error] LLM failed: {resp.error}")
                conversation.pop()
                continue
            raw = resp.text
        except Exception as exc:
            print(f"[Error] LLM failed: {exc}")
            conversation.pop()
            continue

        action = _parse_response(raw)

        response_text = action.get("response")
        if response_text and action.get("action") is None:
            print(f"\nCTO> {response_text}\n")
            conversation.append({"role": "assistant", "content": response_text})
            continue

        tool_name = action.get("action")
        if not tool_name:
            msg = action.get("reasoning", "No action determined.")
            print(f"\nCTO> {msg}\n")
            conversation.append({"role": "assistant", "content": msg})
            continue

        tool_args = action.get("args", {})

        if brain.permissions.is_blocked(tool_name, tool_args):
            msg = f"[Blocked] {tool_name} is not allowed."
            print(f"\nCTO> {msg}\n")
            conversation.append({"role": "assistant", "content": msg})
            continue

        if brain.permissions.requires_approval(tool_name, tool_args):
            confirm = input(f"  Allow {tool_name}({tool_args})? [y/N] ").strip().lower()
            if confirm != "y":
                print("  Skipped.\n")
                continue

        t0 = time.monotonic()
        result = brain.tools.dispatch(tool_name, tool_args)
        elapsed = time.monotonic() - t0

        output = result.output
        if len(output) > 3000:
            output = output[:3000] + "\n... (truncated)"
        safe = output.encode("ascii", errors="replace").decode("ascii")

        status = "OK" if result.success else "FAILED"
        print(f"\nCTO> [{tool_name}] {status} ({elapsed:.1f}s)")
        print(f"{safe[:2000]}\n")

        conversation.append({
            "role": "assistant",
            "content": f"[{tool_name}] {output[:500]}",
        })


def _parse_response(raw: str) -> dict:
    try:
        text = raw.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text)
    except (json.JSONDecodeError, IndexError):
        return {"response": raw.strip(), "action": None}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ARIA Autonomous CTO Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m cto --repo . --interactive
  python -m cto --repo . --provider nvidia --model nvidia/llama-3.3-nemotron-super-49b-v1
  python -m cto --repo . --provider ollama --model deepseek-coder-v2:16b
  python -m cto --repo . --single-cycle
        """,
    )
    parser.add_argument("--repo", default=".", help="Repository path")
    parser.add_argument("--provider", default="nvidia", choices=["ollama", "nvidia"], help="LLM provider")
    parser.add_argument("--model", default="minimaxai/minimax-m2.7", help="Model name")
    parser.add_argument("--api-key", default="", help="API key (falls back to NVIDIA_API_KEY env var)")
    parser.add_argument("--base-url", default="", help="Provider base URL")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama URL (for fallback)")
    parser.add_argument("--single-cycle", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--interactive", action="store_true", help="Interactive chat mode")
    parser.add_argument("--auto-approve", action="store_true", help="Auto-approve operations")
    parser.add_argument("--max-cycles", type=int, default=None, help="Max cycles")
    parser.add_argument("--interval", type=int, default=30, help="Seconds between cycles")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument("--skip-validation", action="store_true", help="Skip environment checks")

    args = parser.parse_args()

    log_level = "DEBUG" if args.verbose else "INFO"
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="[%(levelname)s] [%(name)s] %(message)s",
        stream=sys.stderr,
    )

    repo_path = str(Path(args.repo).resolve())
    if not Path(repo_path).is_dir():
        print(f"Error: {repo_path} is not a directory", file=sys.stderr)
        sys.exit(1)

    fallback_provider = "ollama" if args.provider == "nvidia" else "ollama"
    config = CTOConfig(
        repo_path=repo_path,
        provider=args.provider,
        model=args.model,
        api_key=args.api_key,
        base_url=args.base_url,
        ollama_base_url=args.ollama_url,
        fallback_provider=fallback_provider,
        fallback_model="deepseek-coder-v2:16b",
        cycle_interval_seconds=args.interval,
        max_cycles=args.max_cycles,
        auto_approve=args.auto_approve,
        single_cycle=args.single_cycle,
    )

    if not args.skip_validation:
        issues = _validate_environment(config)
        if issues:
            print("Environment validation failed:\n")
            for issue in issues:
                print(f"  - {issue}")
            print("\nFix the above and retry. Use --skip-validation to bypass.")
            sys.exit(1)

    from .brain import CTOBrain
    brain = CTOBrain(config)

    def _shutdown(signum: int, frame) -> None:
        brain.stop()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        if args.interactive:
            _interactive_mode(brain)
        elif config.single_cycle:
            state = brain.run_single_cycle()
            print(f"\nCycle {state.cycle_id} completed:")
            print(f"  Phase: {state.phase}")
            print(f"  Actions: {len(state.actions_taken)}")
            print(f"  Files modified: {len(state.files_modified)}")
            print(f"  Tests passed: {state.tests_passed}")
            print(f"  Commit: {state.commit_sha or 'none'}")
            print(f"  Error: {state.error or 'none'}")
        else:
            brain.run_continuous()
    finally:
        brain.shutdown()


if __name__ == "__main__":
    main()
