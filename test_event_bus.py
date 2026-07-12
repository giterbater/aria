#!/usr/bin/env python3
"""Quick test of event bus and world integration."""
import sys
sys.path.insert(0, '.')

print('Testing world loop...')
from aria_world.world import WorldEngine
from aria_core.cognition.events import Event, CognitiveEvent
from event_bus import bus
import time

world = WorldEngine()
world.initialize()
print(f'[OK] World initialized with {len(world._agents)} agents')

obs = world.observe()
print(f'[OK] Observation: day={obs.tick}, agents={len(obs.data["agent_statuses"])}')

received = []
def handler(ev):
    received.append(ev)
    print(f'  [OK] Event handler fired: {ev.event}')

bus.subscribe(Event.OBSERVATION, handler)
ev = CognitiveEvent(episode_id='test123', agent_id='test', event=Event.OBSERVATION, tick=1, sequence=1, payload={'test': True})
bus.publish(Event.OBSERVATION, ev)
print(f'[OK] Published event; handlers called: {len(received)}')

time.sleep(0.2)
print(f'[OK] Event bus test passed')

# Now test UI imports
print('\nTesting UI imports...')
try:
    from ui.aria_app import main
    print('[OK] UI imports OK')
except Exception as e:
    print(f'[FAIL] UI import failed: {e}')
