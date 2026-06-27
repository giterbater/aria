"""
Text-mode conversation loop for ARIA.

Runs the perception/cognition loop via stdin/stdout without requiring
microphone input or CustomTkinter UI. Useful for testing and debugging
the decision-making and output planning layers.

Usage:
    from aria_project.text_mode_loop import run_text_loop
    run_text_loop()
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from event_bus import bus
from input_interpreter.factory import build_input_interpreter
from output_planner.factory import build_output_planner
from language_cortex.manager import LanguageCortex
from language_cortex.models.mock import MockModel
from aria_core.decision_maker import SimpleDecisionMaker
from aria_core.memory.simple_memory_system import SimpleMemorySystem
from aria_core.goals import GoalManager, Goal
from aria_core.interfaces import ARIDecision
from output_planner.alang_serialization import alang_to_str

logger = logging.getLogger("aria.text_mode_loop")


def _load_config():
    """Load ARIA configuration (copied from main.py for independence)."""
    import os
    use_mock = not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY").startswith("sk-fake")
    model_cfg = {
        "module": "language_cortex.models.mock",
        "class": "MockModel",
        "args": {}
    } if use_mock else {
        "module": "language_cortex.models.openai",
        "class": "OpenAIModel",
        "args": {
            "api_key": os.getenv("OPENAI_API_KEY"),
            "model": "gpt-4o"
        }
    }
    return {
        "input_interpreter": {
            "type": "rule_based",
            "rule_based": {
                "module": "input_interpreter.implementations.rule_based",
                "class": "RuleBasedInputInterpreter",
                "args": {}
            },
            "confidence_threshold": 0.85
        },
        "output_planner": {
            "type": "rule_based",
            "rule_based": {
                "module": "output_planner.implementations.rule_based",
                "class": "RuleBasedOutputPlanner",
                "args": {}
            }
        },
        "language_model": model_cfg,
    }


def run_text_loop(verbose: bool = True):
    """
    Run ARIA in text-mode conversation loop.
    
    Reads user input from stdin, processes through the full ARIA pipeline
    (interpret → decide → plan → generate), and prints output to stdout.
    
    Args:
        verbose: If True, print debug info (confidence, action type, ALang term).
    
    Usage:
        >>> run_text_loop()
        ARIA Text Mode
        Type 'exit', 'quit', or 'stop' to exit.
        -----
        You: <user input here>
        ARIA: <response>
        -----
        You: ...
    """
    print("\n" + "="*60)
    print("ARIA Text Mode")
    print("Type 'exit', 'quit', or 'stop' to exit.")
    print("="*60 + "\n")

    cfg = _load_config()

    # Build modules
    interp = build_input_interpreter(cfg["input_interpreter"])
    planner = build_output_planner(cfg["output_planner"])

    # Load language model
    model_cfg = cfg["language_model"]
    model_cls = getattr(
        __import__(f"{model_cfg['module']}", fromlist=[model_cfg['class']]),
        model_cfg['class']
    )
    model = model_cls(**model_cfg.get("args", {}))
    cortex = LanguageCortex(model=model)

    # Initialize cognitive systems
    memory = SimpleMemorySystem()
    goals = GoalManager()
    goals.add_goal(Goal(description="Learn Spanish", priority=1.2))
    goals.add_goal(Goal(description="Stay healthy", priority=1.0,
                        deadline=datetime.now() + timedelta(days=30)))
    decision_maker = SimpleDecisionMaker(memory=memory, goals=goals)

    def run_async(coro):
        """Run async code from the sync loop."""
        return asyncio.run(coro)

    def pub(event: str, payload=None):
        """Publish event to bus."""
        bus.publish(event, payload)

    try:
        while True:
            # Read user input
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue

            if user_input.lower() in {"exit", "quit", "stop"}:
                print("\nARIA: Goodbye!")
                break

            try:
                # ---- Input Interpreter ----
                structured = run_async(interp.interpret(user_input))
                if verbose:
                    print(f"  [Intent: {structured.intent}, Confidence: {structured.confidence:.2f}]")

                # ---- ARIA Core (decision maker) ----
                decision: ARIDecision = run_async(decision_maker.decide(structured))
                if verbose:
                    print(f"  [Action: {decision.action_type}]")

                # Create ALang term for debugging
                alang_term = {
                    ":goal": {"id": f"g{int(datetime.now().timestamp())}",
                              "state": decision.action_type},
                    ":act": {decision.action_type: decision.payload}
                }

                # ---- Output Planner ----
                plan = run_async(planner.plan(decision))

                # ---- Language Cortex (generate response text) ----
                if plan.get("speak", True):
                    prompt = plan.get("prompt", str(decision.payload))
                    response = run_async(cortex.chat(
                        prompt,
                        temperature=plan.get("temperature", 0.7),
                        max_tokens=plan.get("max_tokens", 256),
                    ))
                    print(f"\nARIA: {response}")

                    if verbose:
                        print(f"  [ALang: {alang_to_str(alang_term)}]")

                # ---- Memory bookkeeping ----
                pub("MemoryStored", {"working_memory": memory.get_working(limit=5)})
                if len(memory.get_episodic(limit=1000)) % 7 == 0:
                    memory.consolidate(importance_threshold=0.7)
                    memory.forget_low_importance(threshold=0.2)

                # ---- Goal bookkeeping ----
                if decision.action_type == "execute":
                    for g in list(goals.list_goals()):
                        if decision.payload.get("action", "").lower() in g.description.lower():
                            pub("GoalCompleted", {"goal_id": g.id})
                            break

            except KeyboardInterrupt:
                print("\n\nARIA: Interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\nARIA: Error processing input: {e}")
                logger.error(f"Error processing input: {e}", exc_info=True)

    finally:
        print("\nARIA Text Mode ended.\n")


if __name__ == "__main__":
    run_text_loop(verbose=True)
