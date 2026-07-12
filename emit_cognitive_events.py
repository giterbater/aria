"""
Direct cognitive event emulator — publishes a full 9-step cognitive pipeline every tick
to simulate continuous thinking.
"""
import sys
sys.path.insert(0, '.')

import time
import uuid
from datetime import datetime, timezone
from aria_core.cognition.events import Event, CognitiveEvent
from event_bus import bus

def emit_cognitive_cycle(episode_id: str, tick: int):
    """Emit a complete 9-step cognitive pipeline."""
    
    # 1. Observation
    ev = CognitiveEvent(
        episode_id=episode_id,
        agent_id="aria_main",
        event=Event.OBSERVATION,
        tick=tick,
        sequence=1,
        payload={"obs_type": "world_state", "population": 10, "day": tick}
    )
    bus.publish(Event.OBSERVATION, ev)
    print(f"[{tick:03d}] OBSERVATION")
    time.sleep(0.05)
    
    # 2. Memory Retrieved
    ev = CognitiveEvent(
        episode_id=episode_id,
        agent_id="aria_main",
        event=Event.MEMORY_RETRIEVED,
        tick=tick,
        sequence=2,
        payload={"memories_retrieved": 3, "context": "recent_decisions"}
    )
    bus.publish(Event.MEMORY_RETRIEVED, ev)
    print(f"[{tick:03d}] MEMORY_RETRIEVED")
    time.sleep(0.05)
    
    # 3. Hypothesis Generated
    ev = CognitiveEvent(
        episode_id=episode_id,
        agent_id="aria_main",
        event=Event.HYPOTHESIS,
        tick=tick,
        sequence=3,
        payload={"hypothesis": "villagers are seeking food", "confidence": 0.75}
    )
    bus.publish(Event.HYPOTHESIS, ev)
    print(f"[{tick:03d}] HYPOTHESIS")
    time.sleep(0.05)
    
    # 4. Prediction Made
    ev = CognitiveEvent(
        episode_id=episode_id,
        agent_id="aria_main",
        event=Event.PREDICTION,
        tick=tick,
        sequence=4,
        payload={"predicted_outcome": "trade_increase", "confidence": 0.6, "surprise": 0.0}
    )
    bus.publish(Event.PREDICTION, ev)
    print(f"[{tick:03d}] PREDICTION")
    time.sleep(0.05)
    
    # 5. Decision Made
    ev = CognitiveEvent(
        episode_id=episode_id,
        agent_id="aria_main",
        event=Event.DECISION,
        tick=tick,
        sequence=5,
        payload={"decision": "observe_and_wait", "rationale": "gather_more_data"}
    )
    bus.publish(Event.DECISION, ev)
    print(f"[{tick:03d}] DECISION")
    time.sleep(0.05)
    
    # 6. Action Taken
    ev = CognitiveEvent(
        episode_id=episode_id,
        agent_id="aria_main",
        event=Event.ACTION,
        tick=tick,
        sequence=6,
        payload={"action": "wait", "duration": 1}
    )
    bus.publish(Event.ACTION, ev)
    print(f"[{tick:03d}] ACTION")
    time.sleep(0.05)
    
    # 7. Outcome Observed
    ev = CognitiveEvent(
        episode_id=episode_id,
        agent_id="aria_main",
        event=Event.OUTCOME,
        tick=tick,
        sequence=7,
        payload={"outcome": "stable", "reward": 0.5, "importance": 0.3}
    )
    bus.publish(Event.OUTCOME, ev)
    print(f"[{tick:03d}] OUTCOME")
    time.sleep(0.05)
    
    # 8. Learning Completed
    ev = CognitiveEvent(
        episode_id=episode_id,
        agent_id="aria_main",
        event=Event.LEARNING,
        tick=tick,
        sequence=8,
        payload={"learning": "stability_is_safe", "importance_delta": 0.1}
    )
    bus.publish(Event.LEARNING, ev)
    print(f"[{tick:03d}] LEARNING")
    time.sleep(0.05)
    
    # 9. Emotion Updated
    ev = CognitiveEvent(
        episode_id=episode_id,
        agent_id="aria_main",
        event=Event.EMOTION,
        tick=tick,
        sequence=9,
        payload={
            "emotion": {
                "confidence": 0.6,
                "curiosity": 0.5,
                "frustration": 0.1,
                "motivation": 0.7,
                "caution": 0.4,
                "persistence": 0.8,
                "novelty": 0.2,
            },
            "cause": f"learning_from_observation_{tick}"
        }
    )
    bus.publish(Event.EMOTION, ev)
    print(f"[{tick:03d}] EMOTION")
    time.sleep(0.05)

def main():
    print("Cognitive Event Emulator - Starting...")
    print("Publishing continuous 9-step cognitive cycles every 1.5s\n")
    
    tick = 1
    while True:
        try:
            episode_id = uuid.uuid4().hex[:12]
            emit_cognitive_cycle(episode_id, tick)
            print(f"[{tick:03d}] Cycle complete\n")
            time.sleep(1.5)  # Wait 1.5s before next cycle
            tick += 1
        except KeyboardInterrupt:
            print("\nStopping...")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)

if __name__ == '__main__':
    main()
