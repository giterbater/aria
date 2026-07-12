"""
Run the SmallCity world in a live loop and publish Observation cognitive events to the event bus
so the UI can subscribe and render the thought stream and world state.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

from aria_world.world import WorldEngine
from aria_core.cognition.events import Event, CognitiveEvent
from event_bus import bus


def main(tick_delay: float = 0.5):
    world = WorldEngine()
    world.initialize()
    # Optionally set an ARIA-controlled agent
    agent_ids = list(world._agents.keys())
    if agent_ids:
        world._aria_agent_id = agent_ids[0]

    try:
        while True:
            # observe current state
            obs = world.observe(world._aria_agent_id)
            ev = CognitiveEvent(
                episode_id=uuid.uuid4().hex[:12],
                agent_id=obs.agent_id,
                event=Event.OBSERVATION,
                tick=obs.tick,
                sequence=1,
                payload={"obs": obs},
            )
            bus.publish(Event.OBSERVATION, ev)

            # advance the world one tick
            world.tick()

            # small delay so UI has time to render
            time.sleep(tick_delay)
    except KeyboardInterrupt:
        print("Stopping live world loop")


if __name__ == '__main__':
    main()
