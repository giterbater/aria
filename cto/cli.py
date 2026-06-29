from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
from pathlib import Path

from .config import CTOConfig


def _interactive_mode(brain) -> None:
    print("\n=== ARIA CTO Interactive Mode ===")
    print("Type a task and press Enter. Type 'quit' or 'exit' to stop.\n")

    while True:
        try:
            user_input = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye.")
            break

        if brain.llm is None:
            print("[Error] No LLM available. Cannot process requests.")
            continue

        print(f"\n[CTO] Processing: {user_input}")

        import asyncio

        prompt = (
            f"You are ARIA, an autonomous CTO. The user asks you to: {user_input}\n\n"
            f"Available tools (use EXACT names):\n"
            f"- read_file: read a file (args: path)\n"
            f"- search_code: search for patterns (args: pattern, path)\n"
            f"- list_files: list directory contents (args: path)\n"
            f"- get_structure: project tree (args: path)\n"
            f"- run_command: run a shell command (args: command)\n"
            f"- run_tests: run pytest (args: path)\n"
            f"- apply_edit: edit a file (args: path, old_string, new_string)\n"
            f"- create_file: create a file (args: path, content)\n\n"
            f"You MUST use a tool to complete this task. Respond with JSON:\n"
            f'{{"action": "<tool_name>", "args": {{"path": "..."}}, "reasoning": "..."}}\n\n'
            f"Example: To read main.py, respond:\n"
            f'{{"action": "read_file", "args": {{"path": "main.py"}}, "reasoning": "reading the file"}}'
        )

        try:
            raw = asyncio.run(
                brain.llm.generate(prompt, max_tokens=2048, temperature=0.3)
            )
        except Exception as exc:
            print(f"[Error] LLM failed: {exc}")
            continue

        action = _parse_response(raw)

        response_text = action.get("response")
        if response_text and action.get("action") is None:
            print(f"\nCTO> {response_text}\n")
            continue

        tool_name = action.get("action")
        if not tool_name:
            print(f"\nCTO> {action.get('reasoning', 'No action determined.')}\n")
            continue

        tool_args = action.get("args", {})

        if brain.permissions.is_blocked(tool_name, tool_args):
            print(f"\nCTO> [Blocked] {tool_name} is not allowed.\n")
            continue

        if brain.permissions.requires_approval(tool_name, tool_args):
            confirm = input(f"  Allow {tool_name}({tool_args})? [y/N] ").strip().lower()
            if confirm != "y":
                print("  Skipped.\n")
                continue

        result = brain.tools.dispatch(tool_name, tool_args)

        if result.success:
            output = result.output
            if len(output) > 3000:
                output = output[:3000] + "\n... (truncated)"
            safe = output.encode("ascii", errors="replace").decode("ascii")
            print(f"\nCTO> [{tool_name}] {safe[:2000]}\n")
        else:
            safe = result.output.encode("ascii", errors="replace").decode("ascii")
            print(f"\nCTO> [{tool_name} failed] {safe[:1000]}\n")


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
  python -m cto --repo . --single-cycle
  python -m cto --repo . --auto-approve
  python -m cto --repo /path/to/project --model llama3:70b
        """,
    )
    parser.add_argument(
        "--repo",
        default=".",
        help="Path to the repository to manage (default: current directory)",
    )
    parser.add_argument(
        "--model",
        default="deepseek-coder-v2:16b",
        help="Ollama model name (default: deepseek-coder-v2:16b)",
    )
    parser.add_argument(
        "--ollama-url",
        default="http://localhost:11434",
        help="Ollama API base URL (default: http://localhost:11434)",
    )
    parser.add_argument(
        "--single-cycle",
        action="store_true",
        help="Run a single cycle and exit",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Interactive chat mode — talk to the CTO",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Auto-approve all non-blocked operations",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=None,
        help="Maximum number of cycles before stopping",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Seconds between cycles in continuous mode (default: 30)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

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

    config = CTOConfig(
        repo_path=repo_path,
        ollama_base_url=args.ollama_url,
        model=args.model,
        cycle_interval_seconds=args.interval,
        max_cycles=args.max_cycles,
        auto_approve=args.auto_approve,
        single_cycle=args.single_cycle,
    )

    from .brain import CTOBrain
    brain = CTOBrain(config)

    def _shutdown(signum: int, frame) -> None:
        logging.getLogger("aria.cto.cli").info("Received signal %d, stopping...", signum)
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
