"""Debug: test event bus with both publisher and subscriber."""
import sys
sys.path.insert(0, '.')

from aria_core.cognition.events import Event, CognitiveEvent
from event_bus import bus
import threading
import time
import uuid

received_count = [0]

def handler(event):
    received_count[0] += 1
    print(f"Handler called! Total received: {received_count[0]}")

# Subscribe
print("Subscribing to OBSERVATION events...")
bus.subscribe(Event.OBSERVATION, handler)

# Publish
print("Publishing OBSERVATION event...")
ev = CognitiveEvent(
    episode_id=uuid.uuid4().hex[:12],
    agent_id="test",
    event=Event.OBSERVATION,
    tick=1,
    sequence=1,
    payload={"test": True}
)
bus.publish(Event.OBSERVATION, ev)

time.sleep(0.5)
print(f"Total events received: {received_count[0]}")

if received_count[0] == 0:
    print("ERROR: Event bus is not working!")
    print(f"Event.OBSERVATION constant: {Event.OBSERVATION}")
    print(f"Subscribers: {bus._subscribers}")
else:
    print("SUCCESS: Event bus is working!")
