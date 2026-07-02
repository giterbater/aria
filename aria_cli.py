#!/usr/bin/env python3
"""ARIA CLI — Autonomous Engineering Agent

Usage:
    python aria_cli.py objective "analyze the codebase"
    python aria_cli.py objective "find and fix TODO comments"
    python aria_cli.py status
    python aria_cli.py interactive
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from aria_core.orchestrator import CognitiveLoop
from aria_core.cognitive import CognitiveEngine
from aria_core.reasoning import ReasoningEngine
from aria_core.skills import SkillManager
from aria_core.skills.builtin import FileSkill, TerminalSkill, GitSkill
from aria_core.skills.builtin.code_skill import CodeSkill
from aria_core.skills.builtin.doc_skill import DocSkill
from aria_core.reflection import ReflectionEngine, ReflectionStore
from aria_core.learning import LearningEngine, KnowledgeBase
from aria_core.goals import GoalManager


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )


def build_loop(db_path: str, verbose: bool = False) -> CognitiveLoop:
    """Construct all ARIA subsystems and wire them together."""
    reasoning = ReasoningEngine()
    cognitive = CognitiveEngine(reasoning=reasoning, db_path=db_path)

    skills = SkillManager()
    skills.register(FileSkill(base_path="."))
    skills.register(TerminalSkill())
    skills.register(GitSkill(default_cwd="."))
    skills.register(CodeSkill(base_path="."))
    skills.register(DocSkill(base_path="."))

    reflection = ReflectionEngine(store=ReflectionStore(db_path))
    knowledge = KnowledgeBase(db_path)
    learning = LearningEngine(knowledge=knowledge, reflection=reflection, db_path=db_path)
    goals = GoalManager()

    loop = CognitiveLoop(
        cognitive=cognitive,
        skills=skills,
        reflection=reflection,
        learning=learning,
        goals=goals,
    )

    return loop


def cmd_objective(args) -> None:
    """Process a single objective."""
    db_path = str(Path(args.repo) / ".aria" / "cognitive.db")
    loop = build_loop(db_path, verbose=args.verbose)

    print(f"\nARIA > Processing: {args.objective}\n")
    t0 = time.monotonic()

    result = loop.run_objective(args.objective)

    elapsed = time.monotonic() - t0
    status = "SUCCESS" if result["success"] else "FAILED"

    print(f"\n{'='*60}")
    print(f"Result: {status}")
    print(f"Duration: {elapsed:.1f}s")
    print(f"Phases completed: {len(result['phases'])}")
    if result.get("error"):
        print(f"Error: {result['error']}")
    print(f"{'='*60}")

    cognitive_status = loop._cognitive.get_status()
    print(f"\nCognitive State:")
    for key, value in cognitive_status["state"].items():
        if isinstance(value, float):
            print(f"  {key}: {value:.0%}")
        else:
            print(f"  {key}: {value}")

    print(f"\nLearning:")
    print(f"  {loop._learning.get_knowledge_summary()}")

    if args.json:
        print(f"\n{json.dumps(result, indent=2, default=str)}")


def cmd_status(args) -> None:
    """Show ARIA system status."""
    db_path = str(Path(args.repo) / ".aria" / "cognitive.db")
    loop = build_loop(db_path)

    status = loop.get_status()
    print(json.dumps(status, indent=2, default=str))


def cmd_interactive(args) -> None:
    """Interactive mode — type objectives and see results."""
    db_path = str(Path(args.repo) / ".aria" / "cognitive.db")
    loop = build_loop(db_path)

    print("\nARIA Interactive Mode")
    print("Type an objective and press Enter. Type 'quit' to exit.\n")

    while True:
        try:
            user_input = input("ARIA> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            break
        if user_input.lower() == "status":
            status = loop.get_status()
            print(json.dumps(status, indent=2, default=str))
            continue

        result = loop.run_objective(user_input)
        status = "OK" if result["success"] else "FAIL"
        print(f"\n[{status}] {result['duration_ms']}ms, {len(result['phases'])} phases")

        cognitive = loop._cognitive.get_status()
        print(f"  Confidence: {cognitive['state']['confidence']:.0%}")
        print(f"  Frustration: {cognitive['state']['frustration']:.0%}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ARIA — Autonomous Engineering Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--repo", default=".", help="Repository path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--json", action="store_true", help="Output JSON")

    sub = parser.add_subparsers(dest="command")

    obj_parser = sub.add_parser("objective", help="Process a single objective")
    obj_parser.add_argument("objective", help="The objective to process")

    sub.add_parser("status", help="Show system status")
    sub.add_parser("interactive", help="Interactive mode")

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.command == "objective":
        cmd_objective(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "interactive":
        cmd_interactive(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
