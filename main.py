# aria_project/main.py
"""
Entry point:
- Starts the CustomTkinter UI (main thread)
- Runs the perception / cognition loop in a daemon thread
- All modules publish to the shared Event Bus
"""

from __future__ import annotations
import asyncio
import os
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Add the directory containing this file (i.e., the aria_project folder) to sys.path
sys.path.append(str(Path(__file__).parent))

import speech_recognition as sr
import customtkinter as ctk   # only to check availability; UI runs its own mainloop

from aria_logging import logger
from event_bus import bus
from ui.aria_ui import run_ui
from input_interpreter.factory import build_input_interpreter
from output_planner.factory import build_output_planner
from language_cortex.manager import LanguageCortex
from language_cortex.models.mock import MockModel   # fallback
from aria_core.decision_maker import SimpleDecisionMaker
from aria_core.memory.simple_memory_system import SimpleMemorySystem
from aria_core.goals import GoalManager, Goal
from aria_core.interfaces import ARIDecision

# ----------------------------------------------------------------------
# Configuration (same as before – rule‑based only for the demo)
def _load_config() -> dict:
    """Load ARIA configuration."""
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
            "llm_based": {
                "module": "input_interpreter.implementations.llm_based",
                "class": "LLMBasedInputInterpreter",
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

# ----------------------------------------------------------------------
# Background worker – does the actual ARIA processing
def _aria_worker(stop_event: threading.Event) -> None:
    """Run the ARIA cognitive loop in a worker thread."""
    cfg = _load_config()

    # Build modules
    interp = build_input_interpreter(cfg["input_interpreter"])
    planner = build_output_planner(cfg["output_planner"])
    model_cls = getattr(
        __import__(f"{cfg['language_model']['module']}", fromlist=[cfg['language_model']['class']]),
        cfg['language_model']['class']
    )
    model = model_cls(**cfg['language_model'].get("args", {}))
    cortex = LanguageCortex(model=model)
    memory = SimpleMemorySystem()
    goals = GoalManager()
    # optionally seed a couple of goals
    goals.add_goal(Goal(description="Learn Spanish", priority=1.2))
    goals.add_goal(Goal(description="Stay healthy", priority=1.0,
                        deadline=datetime.now() + timedelta(days=30)))
    decision_maker = SimpleDecisionMaker(memory=memory, goals=goals)

    recognizer = sr.Recognizer()
    microphone = sr.Microphone()

    # Helper to publish events
    def pub(ev: str, payload: Any = None) -> None:
        bus.publish(ev, payload)

    def run_async(coro: Any) -> Any:
        """Run one async subsystem call from the synchronous worker thread."""
        return asyncio.run(coro)

    with microphone as source:
        recognizer.adjust_for_ambient_noise(source)
        while not stop_event.is_set():
            try:
                pub("SpeechStarted")
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
                raw = recognizer.recognize_google(audio)
                pub("SpeechRecognized", raw)

                if raw.lower().strip() in {"exit", "quit", "stop"}:
                    pub("SystemStatus", "Shutting down…")
                    break

                # ---- Input Interpreter ----
                structured = run_async(interp.interpret(raw))
                pub("InterpretationReady", {
                    "intent": structured.intent,
                    "confidence": structured.confidence,
                })

                # ---- ARIA Core (decision maker) ----
                decision: ARIDecision = run_async(decision_maker.decide(structured))
                # For debugging we attach a simple ALang rendering of the decision:
                alang_term = {
                    ":goal": {"id": f"g{int(datetime.now().timestamp())}",
                              "state": decision.action_type},
                    ":act": {decision.action_type: decision.payload}
                }
                pub("DecisionMade", {
                    "action_type": decision.action_type,
                    "payload": decision.payload,
                    "response_text": f"ARIA decided: {decision.action_type}",
                    "alang": alang_term,
                })

                # ---- Output Planner ----
                plan = run_async(planner.plan(decision))
                pub("ActionPlanned", plan)

                # ---- Language Cortex (generate spoken text) ----
                if plan.get("speak", True):
                    prompt = plan.get("prompt", str(decision.payload))
                    response = run_async(cortex.chat(
                        prompt,
                        temperature=plan.get("temperature", 0.7),
                        max_tokens=plan.get("max_tokens", 256),
                    ))
                    pub("ResponseGenerated", response)
                    pub("SpeakingStarted")
                    import time
                    time.sleep(min(2.0, len(response) * 0.05))   # rough estimate
                    pub("SpeakingStopped")
                else:
                    pub("SpeakingStarted")
                    pub("SpeakingStopped")

                # ---- Memory bookkeeping ----
                pub("MemoryStored", {"working_memory": memory.get_working(limit=5)})
                if len(memory.get_episodic(limit=1000)) % 7 == 0:
                    memory.consolidate(importance_threshold=0.7)
                    memory.forget_low_importance(threshold=0.2)

                # ---- Goal bookkeeping (example) ----
                if decision.action_type == "execute":
                    for g in list(goals.list_goals()):
                        if decision.payload.get("action", "").lower() in g.description.lower():
                            pub("GoalCompleted", {"goal_id": g.id})
                            break

            except sr.WaitTimeoutError:
                continue
            except sr.UnknownValueError:
                pub("SpeechRecognized", "[unintelligible]")
                continue
            except sr.RequestError as e:
                pub("SystemStatus", f"STT error: {e}")
                continue
            except Exception as e:
                import traceback
                logger.error(f"Unexpected error: {e}")
                traceback.print_exc()
                pub("SystemStatus", f"Error: {e}")
                break

    logger.info("Worker thread ending")

# ----------------------------------------------------------------------
# Main – launch UI and worker thread
def main() -> None:
    """Launch ARIA UI and background worker."""
    stop_event = threading.Event()
    worker = threading.Thread(target=_aria_worker, args=(stop_event,), daemon=True)
    worker.start()
    logger.info("Starting ARIA UI")
    try:
        run_ui()          # blocks until the user closes the window
    finally:
        logger.info("UI closed, signalling worker to stop")
        stop_event.set()
        worker.join(timeout=2)
        logger.info("Cleanup done")

if __name__ == "__main__":
    main()
