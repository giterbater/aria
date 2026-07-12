"""Event system — random events, conflicts, opportunities."""

from __future__ import annotations

import random as _random
from dataclasses import dataclass, field
from typing import Any

from .models import ResourceType, AgentState, WorldState
from .config import SimulationConfig


@dataclass
class Event:
    name: str
    description: str
    effects: dict[str, Any] = field(default_factory=dict)
    duration_days: int = 1
    affected_agents: list[str] = field(default_factory=list)


EVENT_POOL: list[dict[str, Any]] = [
    {
        "name": "Food Shortage",
        "description": "A drought has reduced food supplies.",
        "effects": {"food_regen_mult": 0.5, "hunger_boost": 15},
        "duration_days": 3,
    },
    {
        "name": "Storm",
        "description": "A violent storm damages resources.",
        "effects": {"wood_loss": 30, "food_loss": 20, "safety_drop": 20},
        "duration_days": 2,
    },
    {
        "name": "Traveling Merchant",
        "description": "A merchant arrives with rare goods.",
        "effects": {"iron_bonus": 20, "trade_opportunity": True},
        "duration_days": 1,
    },
    {
        "name": "Bountiful Harvest",
        "description": "Excellent conditions for farming.",
        "effects": {"food_regen_mult": 2.0, "food_bonus": 30},
        "duration_days": 2,
    },
    {
        "name": "Illness",
        "description": "A sickness spreads through the village.",
        "effects": {"energy_drop": 25, "safety_drop": 10},
        "duration_days": 3,
        "affects_random": True,
    },
    {
        "name": "Bandit Attack",
        "description": "Bandits threaten the village.",
        "effects": {"safety_drop": 30, "food_loss": 15, "iron_loss": 10},
        "duration_days": 1,
    },
    {
        "name": "Water Surge",
        "description": "Spring waters overflow.",
        "effects": {"water_bonus": 50, "water_regen_mult": 1.5},
        "duration_days": 2,
    },
    {
        "name": "Iron Vein Discovered",
        "description": "A new iron deposit is found nearby.",
        "effects": {"iron_bonus": 40},
        "duration_days": 1,
    },
]


class EventSystem:
    def __init__(self, config: SimulationConfig, rng: _random.Random | None = None) -> None:
        self._config = config
        self._rng = rng or _random.Random()
        self._active_events: list[Event] = []

    def maybe_generate_event(self, day: int, world: WorldState) -> Event | None:
        if self._rng.random() > self._config.event_probability:
            return None
        template = self._rng.choice(EVENT_POOL)
        event = Event(
            name=template["name"],
            description=template["description"],
            effects=dict(template["effects"]),
            duration_days=template.get("duration_days", 1),
        )
        if template.get("affects_random"):
            event.affected_agents = ["random"]
        self._active_events.append(event)
        world.events_history.append({"day": day, "event": event.name, "description": event.description})
        return event

    def apply_event(self, event: Event, agents: list[AgentState], world: WorldState) -> list[str]:
        logs: list[str] = []
        effects = event.effects

        if "wood_loss" in effects:
            world.resources[ResourceType.WOOD] = max(0, world.resources.get(ResourceType.WOOD, 0) - effects["wood_loss"])
            logs.append(f"Lost {effects['wood_loss']} wood")
        if "food_loss" in effects:
            world.resources[ResourceType.FOOD] = max(0, world.resources.get(ResourceType.FOOD, 0) - effects["food_loss"])
            logs.append(f"Lost {effects['food_loss']} food")
        if "iron_loss" in effects:
            world.resources[ResourceType.IRON] = max(0, world.resources.get(ResourceType.IRON, 0) - effects["iron_loss"])
        if "food_bonus" in effects:
            world.resources[ResourceType.FOOD] = world.resources.get(ResourceType.FOOD, 0) + effects["food_bonus"]
            logs.append(f"Gained {effects['food_bonus']} food")
        if "water_bonus" in effects:
            world.resources[ResourceType.WATER] = world.resources.get(ResourceType.WATER, 0) + effects["water_bonus"]
        if "iron_bonus" in effects:
            world.resources[ResourceType.IRON] = world.resources.get(ResourceType.IRON, 0) + effects["iron_bonus"]

        if "safety_drop" in effects:
            for agent in agents:
                agent.needs.safety = max(0, agent.needs.safety - effects["safety_drop"])
        if "energy_drop" in effects:
            for agent in agents:
                agent.needs.energy = max(0, agent.needs.energy - effects["energy_drop"])
        if "hunger_boost" in effects:
            for agent in agents:
                agent.needs.hunger = min(100, agent.needs.hunger + effects["hunger_boost"])

        logs.append(f"Event: {event.name} — {event.description}")
        return logs

    def tick_active_events(self) -> dict[str, float]:
        modifiers: dict[str, float] = {}
        remaining: list[Event] = []
        for event in self._active_events:
            if event.duration_days > 0:
                if "food_regen_mult" in event.effects:
                    modifiers["food_regen_mult"] = event.effects["food_regen_mult"]
                if "water_regen_mult" in event.effects:
                    modifiers["water_regen_mult"] = event.effects["water_regen_mult"]
                event.duration_days -= 1
                if event.duration_days > 0:
                    remaining.append(event)
        self._active_events = remaining
        return modifiers

    def check_conflict_triggers(self, agents: list[AgentState]) -> list[tuple[str, str]]:
        conflicts: list[tuple[str, str]] = []
        hungry = [a for a in agents if a.alive and a.needs.hunger > 70 and a.personality.aggression > 0.6]
        for i, a in enumerate(hungry):
            for b in hungry[i + 1:]:
                if a.needs.hunger > 70 and b.needs.hunger > 70:
                    conflicts.append((a.id, b.id))
        return conflicts
