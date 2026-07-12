"""
ARIA Cognitive OS UI with integrated event emitter.
The emitter runs as a background thread, so they share the same event_bus instance.
"""
import sys
sys.path.insert(0, '.')

from ui.aria_app import CognitiveOSUI
import threading
import time
import uuid
from datetime import datetime, timezone
from aria_core.cognition.events import Event, CognitiveEvent
from event_bus import bus
from PySide6.QtWidgets import QApplication


def emit_cognitive_cycle(episode_id: str, tick: int):
    """Emit a complete 9-step cognitive pipeline."""
    
    events_to_emit = [
        (Event.OBSERVATION, 1, {"obs_type": "world_state", "population": 10, "day": tick}),
        (Event.MEMORY_RETRIEVED, 2, {"memories_retrieved": 3, "context": "recent_decisions"}),
        (Event.HYPOTHESIS, 3, {"hypothesis": "villagers are seeking food", "confidence": 0.75}),
        (Event.PREDICTION, 4, {"predicted_outcome": "trade_increase", "confidence": 0.6, "surprise": 0.0}),
        (Event.DECISION, 5, {"decision": "observe_and_wait", "rationale": "gather_more_data"}),
        (Event.ACTION, 6, {"action": "wait", "duration": 1}),
        (Event.OUTCOME, 7, {"outcome": "stable", "reward": 0.5, "importance": 0.3}),
        (Event.LEARNING, 8, {"learning": "stability_is_safe", "importance_delta": 0.1}),
        (Event.EMOTION, 9, {
            "emotion": {
                "confidence": 0.6 + (tick % 3) * 0.1,
                "curiosity": 0.5 + (tick % 5) * 0.05,
                "frustration": 0.1,
                "motivation": 0.7,
                "caution": 0.4,
                "persistence": 0.8,
                "novelty": 0.2 + (tick % 4) * 0.1,
            },
            "cause": f"learning_from_observation_{tick}"
        }),
    ]
    
    for event_name, sequence, payload in events_to_emit:
        ev = CognitiveEvent(
            episode_id=episode_id,
            agent_id="aria_main",
            event=event_name,
            tick=tick,
            sequence=sequence,
            payload=payload
        )
        bus.publish(event_name, ev)
        time.sleep(0.08)  # Small delay between events for visibility


def emitter_thread_func():
    """Background thread that emits cognitive cycles."""
    print("[EMITTER] Started")
    tick = 1
    while True:
        try:
            episode_id = uuid.uuid4().hex[:12]
            emit_cognitive_cycle(episode_id, tick)
            print(f"[EMITTER] Cycle {tick} complete")
            time.sleep(1.5)  # Wait 1.5s before next cycle
            tick += 1
        except Exception as e:
            print(f"[EMITTER] Error: {e}")
            time.sleep(1)


def main():
    app = QApplication(sys.argv)
    
    # Start emitter in background thread
    emitter = threading.Thread(target=emitter_thread_func, daemon=True)
    emitter.start()
    print("[MAIN] Emitter thread started")
    
    # Create and show UI
    window = CognitiveOSUI()
    window.show()
    print("[MAIN] UI window shown")
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
