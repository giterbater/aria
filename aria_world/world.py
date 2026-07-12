"""WorldEngine — tick loop, resources, conflict, trade, reproduction, culture, innovation."""

from __future__ import annotations

import logging
import random as _random
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

from aria_core.environment import (
    Action,
    ActionSchema,
    AgentSnapshot,
    BuildingSnapshot,
    EnvironmentSpec,
    Observation,
    RoadSegment,
    WorldEvent,
    WorldSnapshot,
    validate_action_for_environment,
)

from .models import ResourceType, Occupation, AgentState, WorldState, Family
from .config import SimulationConfig
from .resources import ResourceSystem
from .needs import NeedsSystem
from .relationships import RelationshipGraph
from .events import EventSystem
from .reproduction import ReproductionSystem
from .knowledge_sharing import KnowledgeSharingSystem
from .expertise import ExpertiseSystem
from .culture import CultureSystem
from .innovation import InnovationSystem
from .agent import VillageAgent, AgentDependencies

logger = logging.getLogger("aria_world.world")

VILLAGE_NAMES = [
    "Aria", "Bob", "Cara", "Dex", "Ella",
    "Finn", "Gia", "Hank", "Iris", "Jake",
    "Kira", "Leo", "Mara", "Nate", "Opal",
    "Pete", "Quinn", "Rosa", "Seth", "Tara",
]


class WorldEngine:
    def __init__(self, config: SimulationConfig | None = None) -> None:
        self.config = config or SimulationConfig()
        self._seed = self.config.seed if self.config.seed is not None else 42
        self._rng = _random.Random(self._seed)

        self.world_state = WorldState()
        self.resource_system = ResourceSystem(self.config, self._rng)
        self.needs_system = NeedsSystem(self.config, self._rng)
        self.relationship_graph = RelationshipGraph()
        self.event_system = EventSystem(self.config, self._rng)
        self.reproduction_system = ReproductionSystem(self.config, self._rng)
        self.knowledge_sharing = KnowledgeSharingSystem(self._rng)
        self.expertise = ExpertiseSystem(self._rng)
        self.culture = CultureSystem(self._rng)
        self.innovation = InnovationSystem(self._rng)

        self._agents: dict[str, VillageAgent] = {}
        self._agent_positions: dict[str, dict[str, float]] = {}
        self._aria_agent_id: str | None = None
        self._focused_agent_id: str | None = None
        self._deps = AgentDependencies(
            resource_system=self.resource_system,
            needs_system=self.needs_system,
            relationship_graph=self.relationship_graph,
            world_resources=self.world_state.resources,
            rng=self._rng,
            knowledge_sharing=self.knowledge_sharing,
            expertise=self.expertise,
            culture=self.culture,
            innovation=self.innovation,
        )

    def initialize(self) -> None:
        self.world_state.resources = self.resource_system.initialize_world_resources()

        occupations = list(Occupation)
        names = list(VILLAGE_NAMES)
        self._rng.shuffle(names)

        for i in range(self.config.initial_agents):
            name = names[i % len(names)]
            age = self._rng.randint(*self.config.starting_age_range)
            money = self._rng.uniform(*self.config.starting_money_range)
            occ = occupations[i % len(occupations)]

            from .models import Personality, AgentNeeds
            personality = Personality(
                aggression=self._rng.uniform(0.2, 0.8),
                generosity=self._rng.uniform(0.2, 0.8),
                diligence=self._rng.uniform(0.3, 0.9),
                curiosity=self._rng.uniform(0.2, 0.8),
                sociability=self._rng.uniform(0.2, 0.8),
            )

            state = AgentState(
                name=name,
                age=age,
                money=money,
                inventory=self.resource_system.initialize_agent_inventory(occ),
                needs=AgentNeeds(
                    hunger=self._rng.uniform(30, 60),
                    sleep=self._rng.uniform(30, 50),
                    energy=self._rng.uniform(60, 90),
                    safety=self._rng.uniform(50, 80),
                    social=self._rng.uniform(30, 60),
                ),
                occupation=occ,
                personality=personality,
            )

            agent = VillageAgent(state, self.config, self._deps)
            self._agents[state.id] = agent
            self._agent_positions[state.id] = self._initial_position(state)
            self.relationship_graph.add_agent(state.id)

            skill_name = occ.value
            base_level = 0.2 + (age - 20) * 0.01 if age > 20 else 0.1
            self.knowledge_sharing.add_knowledge(
                state.id, skill_name, level=min(0.8, base_level),
            )
            self.expertise.get_profile(state.id, skill_name).level = min(0.8, base_level)

        agent_ids = list(self._agents.keys())
        for i, a_id in enumerate(agent_ids):
            for b_id in agent_ids[i + 1:]:
                trust = self._rng.uniform(40, 70)
                self.relationship_graph.initialize_pair(a_id, b_id, trust)

        self.world_state.population_history.append(len(self._agents))

    def reset(self, seed: int | None = None) -> Observation:
        config = replace(self.config, seed=seed) if seed is not None else self.config
        if self._agents:
            self.shutdown()
        self.__init__(config)
        self.initialize()
        return self.observe()

    def step(self, action: Action) -> tuple[Observation, float, bool, dict]:
        self._ensure_initialized()

        validation = validate_action_for_environment(self, action)
        if not validation.valid:
            return (
                self.observe(action.agent_id),
                0.0,
                self._is_done(),
                {"accepted": False, "reason": validation.reason},
            )

        action_result = self._apply_environment_action(action)
        if not action_result.get("accepted", False):
            return (
                self.observe(action.agent_id),
                0.0,
                self._is_done(),
                action_result,
            )

        before_alive = sum(1 for agent in self._agents.values() if agent.is_alive())
        tick_result = self.tick()
        reward = self._reward_from_tick(tick_result, before_alive)
        action_result["result"] = tick_result

        return self.observe(action.agent_id), reward, self._is_done(), action_result

    def observe(self, agent_id: str | None = None) -> Observation:
        self._ensure_initialized()
        subject_id = agent_id or self._aria_agent_id or self._first_alive_agent_id() or "world"
        alive_agents = [agent for agent in self._agents.values() if agent.is_alive()]
        resources = self._resources_as_dict()
        population = len(alive_agents)
        max_population = max(self.config.max_agents, 1)
        scarcity = 1.0 - min(1.0, resources.get("food", 0.0) / max(self.config.initial_resources.get("food", 1.0), 1.0))

        return Observation(
            agent_id=subject_id,
            tick=self.world_state.day,
            timestamp=datetime.now(timezone.utc),
            data={
                "day": self.world_state.day,
                "alive_count": population,
                "resources": resources,
                "agent_statuses": [agent.status() | {"id": agent.state.id} for agent in self._agents.values()],
                "agent_positions": self._position_snapshots(),
                "trust_edges": self._trust_snapshots(),
                "focused_agent_id": self._focused_agent_id,
                "aria_agent_id": self._aria_agent_id,
                "knowledge_stats": self.knowledge_sharing.get_village_knowledge_stats(),
                "culture_stats": self.culture.get_culture_stats(),
                "innovation_stats": self.innovation.get_innovation_stats(),
            },
            salience={
                "population": population / max_population,
                "scarcity": max(0.0, min(1.0, scarcity)),
                "conflict_pressure": min(1.0, self.world_state.total_conflicts / max(self.world_state.day, 1)),
            },
        )

    def get_state(self) -> WorldSnapshot:
        self._ensure_initialized()
        alive_agents = [agent for agent in self._agents.values() if agent.is_alive()]
        average_happiness = sum(agent.happiness() for agent in alive_agents) / max(len(alive_agents), 1)

        return WorldSnapshot(
            tick=self.world_state.day,
            time_of_day=12.0,
            day=self.world_state.day,
            season=self._season_for_day(self.world_state.day),
            weather="temperate",
            agents=self._agent_snapshots(),
            resources=self._resources_as_dict(),
            buildings=self._building_snapshots(),
            roads=self._road_snapshots(),
            events=self._event_snapshots(),
            metrics={
                "population": float(len(alive_agents)),
                "average_happiness": average_happiness,
                "total_births": float(self.world_state.total_births),
                "total_conflicts": float(self.world_state.total_conflicts),
                "total_trades": float(self.world_state.total_trades),
            },
        )

    def list_actions(self) -> list[ActionSchema]:
        return [
            ActionSchema(
                action_type="wait",
                description="Advance the environment one tick with no direct intervention.",
            ),
            ActionSchema(
                action_type="observe",
                description="Advance one tick while focusing observation on an optional agent.",
                parameters={"agent_id": {"type": "string"}},
            ),
            ActionSchema(
                action_type="focus_agent",
                description="Set the agent highlighted in environment snapshots.",
                parameters={"agent_id": {"type": "string"}},
                required_params=("agent_id",),
            ),
            ActionSchema(
                action_type="set_aria_agent",
                description="Mark one existing world agent as ARIA-controlled for UI snapshots.",
                parameters={"agent_id": {"type": "string"}},
                required_params=("agent_id",),
            ),
        ]

    def render(self, mode: str = "ui") -> Any:
        snapshot = self.get_state()
        if mode in {"ui", "snapshot", "dict"}:
            return asdict(snapshot)
        if mode == "text":
            return {
                "day": snapshot.day,
                "population": len(snapshot.agents),
                "resources": snapshot.resources,
            }
        raise ValueError(f"Unsupported render mode: {mode}")

    def spec(self) -> EnvironmentSpec:
        return EnvironmentSpec(
            name="SmallCity-v0",
            version="0.1.0",
            observation_space={
                "type": "object",
                "properties": {
                    "day": {"type": "integer"},
                    "alive_count": {"type": "integer"},
                    "resources": {"type": "object"},
                    "agent_statuses": {"type": "array"},
                    "agent_positions": {"type": "array"},
                },
            },
            action_space=self.list_actions(),
            max_ticks=self.config.max_days,
            population_range=(0, self.config.max_agents),
            description="ARIA World small-city village simulation adapter.",
        )

    def tick(self) -> dict:
        self.world_state.day += 1
        day = self.world_state.day

        self.resource_system.regen_world_resources(self.world_state.resources)
        event_modifiers = self.event_system.tick_active_events()

        alive_agents = [a for a in self._agents.values() if a.is_alive()]
        day_results = []

        for agent in alive_agents:
            result = agent.live_one_day(day)
            day_results.append(result)

        deaths = [r for r in day_results if not r.get("alive")]
        for death in deaths:
            agent = self._get_agent_by_name(death["agent"])
            if agent:
                self._remove_agent(agent, death.get("cause", "unknown"))

        event = self.event_system.maybe_generate_event(day, self.world_state)
        event_logs: list[str] = []
        if event:
            alive_agents = [a for a in self._agents.values() if a.is_alive()]
            event_logs = self.event_system.apply_event(event, [a.state for a in alive_agents], self.world_state)

        conflicts = self.event_system.check_conflict_triggers([a.state for a in alive_agents])
        conflict_logs: list[str] = []
        for a_id, b_id in conflicts[:2]:
            log = self._resolve_conflict(a_id, b_id, day)
            if log:
                conflict_logs.append(log)

        births = self._check_reproduction(day)

        aging_logs = self._age_agents()
        self._update_positions(day)

        alive_count = sum(1 for a in self._agents.values() if a.is_alive())
        self.world_state.population_history.append(alive_count)

        return {
            "day": day,
            "alive_count": alive_count,
            "deaths": len(deaths),
            "births": births,
            "trades": sum(1 for r in day_results if r.get("produced", {}).get("produced")),
            "conflicts": len(conflicts),
            "events": event_logs,
            "conflict_logs": conflict_logs,
            "agent_statuses": [a.status() | {"id": a.state.id} for a in self._agents.values()],
            "agent_positions": self._position_snapshots(),
            "trust_edges": self._trust_snapshots(),
            "resources": {r.value: q for r, q in self.world_state.resources.items()},
            "knowledge_stats": self.knowledge_sharing.get_village_knowledge_stats(),
            "culture_stats": self.culture.get_culture_stats(),
            "innovation_stats": self.innovation.get_innovation_stats(),
        }

    def run(self, days: int | None = None) -> dict:
        days = days or self.config.max_days
        all_results: list[dict] = []
        for _ in range(days):
            if not any(a.is_alive() for a in self._agents.values()):
                break
            result = self.tick()
            all_results.append(result)
        return self._compile_results(all_results)

    def _resolve_conflict(self, a_id: str, b_id: str, day: int) -> str | None:
        a = self._agents.get(a_id)
        b = self._agents.get(b_id)
        if not a or not b or not a.is_alive() or not b.is_alive():
            return None

        a_aggr = a.state.personality.aggression
        b_aggr = b.state.personality.aggression
        trust = self.relationship_graph.get_trust(a_id, b_id)

        if trust > 40 and (a_aggr < 0.6 or b_aggr < 0.6):
            self.relationship_graph.record_socialize(a_id, b_id, day)
            a.state.needs.social = max(0, a.state.needs.social - 10)
            b.state.needs.social = max(0, b.state.needs.social - 10)
            self.world_state.total_conflicts += 1
            return f"Day {day}: {a.state.name} and {b.state.name} negotiated peacefully"

        self.relationship_graph.record_conflict(a_id, b_id, day)
        self.world_state.total_conflicts += 1

        if a_aggr > b_aggr:
            loser, winner = b, a
        else:
            loser, winner = a, b

        if loser.state.inventory.has(ResourceType.FOOD, 2):
            loser.state.inventory.remove(ResourceType.FOOD, 2)
            winner.state.inventory.add(ResourceType.FOOD, 2)
            return f"Day {day}: {winner.state.name} won conflict, took food from {loser.state.name}"

        loser.state.needs.safety = max(0, loser.state.needs.safety - 20)
        return f"Day {day}: {a.state.name} and {b.state.name} had a confrontation"

    def _check_reproduction(self, day: int) -> int:
        alive = [a.state for a in self._agents.values() if a.is_alive() and a.state.age >= 18]
        if len(alive) < 2:
            return 0

        def trust_fn(a_id: str, b_id: str) -> float:
            return self.relationship_graph.get_trust(a_id, b_id)

        pairs = self.reproduction_system.check_reproduction_opportunities(alive, trust_fn)
        births = 0

        for a_id, b_id in pairs:
            if len(self._agents) >= self.config.max_agents:
                break
            parent_a = self._agents.get(a_id)
            parent_b = self._agents.get(b_id)
            if not parent_a or not parent_b:
                continue
            if not parent_a.is_alive() or not parent_b.is_alive():
                continue

            child_state = self.reproduction_system.create_child(
                parent_a.state, parent_b.state, day,
            )
            child_agent = VillageAgent(child_state, self.config, self._deps)
            self._agents[child_state.id] = child_agent
            parent_pos = self._agent_positions.get(parent_a.state.id, self._initial_position(child_state))
            self._agent_positions[child_state.id] = {
                "x": min(0.95, max(0.05, parent_pos["x"] + self._rng.uniform(-0.04, 0.04))),
                "y": min(0.95, max(0.05, parent_pos["y"] + self._rng.uniform(-0.04, 0.04))),
            }
            self.relationship_graph.add_agent(child_state.id)

            self.relationship_graph.initialize_pair(child_state.id, a_id, 70.0, day)
            self.relationship_graph.initialize_pair(child_state.id, b_id, 70.0, day)

            family = Family(parent_a=a_id, parent_b=b_id, children=[child_state.id], formed_day=day)
            self.world_state.families.append(family)
            self.world_state.total_births += 1
            births += 1

        return births

    def _age_agents(self) -> list[str]:
        logs: list[str] = []
        for agent in list(self._agents.values()):
            if agent.is_alive() and agent.state.age >= 1:
                self.reproduction_system.tick_child(agent.state)
        return logs

    def _remove_agent(self, agent: VillageAgent, cause: str) -> None:
        agent.state.alive = False
        agent.state.cause_of_death = cause

    def _initial_position(self, state: AgentState) -> dict[str, float]:
        occupation_anchor = {
            Occupation.FARMER: (0.30, 0.62),
            Occupation.BUILDER: (0.52, 0.44),
            Occupation.HUNTER: (0.72, 0.34),
            Occupation.MERCHANT: (0.48, 0.68),
            Occupation.BLACKSMITH: (0.62, 0.55),
        }.get(state.occupation, (0.5, 0.5))
        return {
            "x": min(0.95, max(0.05, occupation_anchor[0] + self._rng.uniform(-0.12, 0.12))),
            "y": min(0.95, max(0.05, occupation_anchor[1] + self._rng.uniform(-0.12, 0.12))),
        }

    def _update_positions(self, day: int) -> None:
        for agent in self._agents.values():
            pos = self._agent_positions.setdefault(agent.state.id, self._initial_position(agent.state))
            if not agent.is_alive():
                continue
            urgency, value = agent.state.needs.most_urgent()
            target = {
                "hunger": (0.28, 0.66),
                "sleep": (0.50, 0.50),
                "energy": (0.50, 0.50),
                "safety": (0.40, 0.42),
                "social": (0.54, 0.70),
            }.get(urgency, (0.5, 0.5))
            occupation_pull = {
                Occupation.FARMER: (0.22, 0.72),
                Occupation.BUILDER: (0.52, 0.42),
                Occupation.HUNTER: (0.78, 0.30),
                Occupation.MERCHANT: (0.58, 0.72),
                Occupation.BLACKSMITH: (0.64, 0.52),
            }.get(agent.state.occupation, (0.5, 0.5))
            weight = min(0.12, 0.03 + value / 1000.0)
            drift_x = self._rng.uniform(-0.025, 0.025)
            drift_y = self._rng.uniform(-0.025, 0.025)
            pos["x"] = min(0.96, max(0.04, pos["x"] * (1 - weight) + target[0] * weight * 0.6 + occupation_pull[0] * weight * 0.4 + drift_x))
            pos["y"] = min(0.96, max(0.04, pos["y"] * (1 - weight) + target[1] * weight * 0.6 + occupation_pull[1] * weight * 0.4 + drift_y))

    def _position_snapshots(self) -> list[dict]:
        snapshots = []
        for agent in self._agents.values():
            pos = self._agent_positions.get(agent.state.id) or self._initial_position(agent.state)
            snapshots.append({
                "id": agent.state.id,
                "name": agent.state.name,
                "x": round(pos["x"], 4),
                "y": round(pos["y"], 4),
                "alive": agent.state.alive,
                "occupation": agent.state.occupation.value,
                "happiness": agent.state.happiness(),
            })
        return snapshots

    def _trust_snapshots(self) -> list[dict]:
        edges = []
        agent_ids = list(self._agents.keys())
        for i, a_id in enumerate(agent_ids):
            for b_id in agent_ids[i + 1:]:
                trust = self.relationship_graph.get_trust(a_id, b_id)
                if trust >= 45:
                    edges.append({
                        "source": a_id,
                        "target": b_id,
                        "trust": round(trust, 2),
                    })
        return edges

    def _get_agent_by_name(self, name: str) -> VillageAgent | None:
        for agent in self._agents.values():
            if agent.state.name == name:
                return agent
        return None

    def get_alive_agents(self) -> list[VillageAgent]:
        return [a for a in self._agents.values() if a.is_alive()]

    def get_agent(self, agent_id: str) -> VillageAgent | None:
        return self._agents.get(agent_id)

    def any_alive(self) -> bool:
        return any(a.is_alive() for a in self._agents.values())

    def _ensure_initialized(self) -> None:
        if not self._agents and not self.world_state.population_history:
            self.initialize()

    def _first_alive_agent_id(self) -> str | None:
        for agent in self._agents.values():
            if agent.is_alive():
                return agent.state.id
        return None

    def _apply_environment_action(self, action: Action) -> dict:
        if action.action_type in {"wait", "observe"}:
            if action.params.get("agent_id"):
                self._focused_agent_id = action.params["agent_id"]
            return {"accepted": True, "action_type": action.action_type}

        if action.action_type == "focus_agent":
            agent_id = action.params["agent_id"]
            if agent_id not in self._agents:
                return {"accepted": False, "reason": f"Unknown agent_id '{agent_id}'"}
            self._focused_agent_id = agent_id
            return {"accepted": True, "action_type": action.action_type, "focused_agent_id": agent_id}

        if action.action_type == "set_aria_agent":
            agent_id = action.params["agent_id"]
            if agent_id not in self._agents:
                return {"accepted": False, "reason": f"Unknown agent_id '{agent_id}'"}
            self._aria_agent_id = agent_id
            self._focused_agent_id = agent_id
            return {"accepted": True, "action_type": action.action_type, "aria_agent_id": agent_id}

        return {"accepted": False, "reason": f"Unsupported action_type '{action.action_type}'"}

    def _reward_from_tick(self, tick_result: dict, before_alive: int) -> float:
        alive_count = float(tick_result.get("alive_count", 0))
        survival_reward = alive_count / max(self.config.initial_agents, 1)
        birth_reward = float(tick_result.get("births", 0)) * 0.1
        death_penalty = max(0, before_alive - int(alive_count)) * 0.2
        conflict_penalty = float(tick_result.get("conflicts", 0)) * 0.05
        return survival_reward + birth_reward - death_penalty - conflict_penalty

    def _is_done(self) -> bool:
        return not self.any_alive() or self.world_state.day >= self.config.max_days

    def _resources_as_dict(self) -> dict[str, float]:
        return {
            resource.value if hasattr(resource, "value") else str(resource): float(quantity)
            for resource, quantity in self.world_state.resources.items()
        }

    def _agent_snapshots(self) -> list[AgentSnapshot]:
        snapshots: list[AgentSnapshot] = []
        for agent in self._agents.values():
            pos = self._agent_positions.get(agent.state.id) or self._initial_position(agent.state)
            urgent_need, urgency = agent.state.needs.most_urgent()
            snapshots.append(
                AgentSnapshot(
                    id=agent.state.id,
                    name=agent.state.name,
                    occupation=agent.state.occupation.value,
                    position=(round(pos["x"], 4), round(pos["y"], 4)),
                    mood={
                        "happiness": agent.happiness(),
                        "urgency": min(1.0, urgency / 100.0),
                    },
                    current_task=urgent_need,
                    inventory=agent.state.inventory.to_dict(),
                    alive=agent.state.alive,
                    is_aria=agent.state.id == self._aria_agent_id,
                )
            )
        return snapshots

    def _building_snapshots(self) -> list[BuildingSnapshot]:
        buildings: list[BuildingSnapshot] = []
        for index, (kind, count) in enumerate(sorted(self.world_state.buildings.items())):
            buildings.append(
                BuildingSnapshot(
                    id=f"building_{kind}",
                    kind=str(kind),
                    position=(0.18 + (index % 5) * 0.16, 0.22 + (index // 5) * 0.14),
                    label=str(kind),
                    occupants=int(count),
                    metadata={"count": count},
                )
            )
        return buildings

    def _road_snapshots(self) -> list[RoadSegment]:
        return [
            RoadSegment(id="village_path_north_south", start=(0.50, 0.08), end=(0.50, 0.92), kind="path"),
            RoadSegment(id="village_path_east_west", start=(0.08, 0.62), end=(0.92, 0.62), kind="path"),
        ]

    def _event_snapshots(self) -> list[WorldEvent]:
        events: list[WorldEvent] = []
        for index, event in enumerate(self.world_state.events_history[-25:]):
            events.append(
                WorldEvent(
                    id=f"world_event_{index}",
                    tick=int(event.get("day", self.world_state.day)),
                    event_type=str(event.get("event", "event")),
                    description=str(event.get("description", "")),
                    severity=0.5,
                    active=False,
                    metadata=dict(event),
                )
            )
        return events

    @staticmethod
    def _season_for_day(day: int) -> str:
        seasons = ("spring", "summer", "autumn", "winter")
        return seasons[((max(day, 1) - 1) // 90) % len(seasons)]

    def _compile_results(self, daily_results: list[dict]) -> dict:
        alive_agents = [a for a in self._agents.values() if a.is_alive()]
        all_agents = list(self._agents.values())

        avg_happiness = sum(a.happiness() for a in alive_agents) / max(len(alive_agents), 1)
        avg_lifespan = sum(a.state.days_survived for a in all_agents) / max(len(all_agents), 1)
        avg_knowledge = sum(a.state.knowledge_entries for a in alive_agents) / max(len(alive_agents), 1)

        survival_rate = len(alive_agents) / max(len(all_agents), 1)

        knowledge_stats = self.knowledge_sharing.get_village_knowledge_stats()
        expertise_stats = self.expertise.get_village_expertise_stats()
        culture_stats = self.culture.get_culture_stats()
        innovation_stats = self.innovation.get_innovation_stats()

        total_days = self.world_state.day
        return {
            "seed": self._seed,
            "days_run": total_days,
            "initial_population": self.config.initial_agents,
            "final_population": len(alive_agents),
            "total_ever": len(all_agents),
            "survival_rate": survival_rate,
            "average_happiness": avg_happiness,
            "average_lifespan_days": avg_lifespan,
            "average_knowledge": avg_knowledge,
            "total_trades": self.world_state.total_trades,
            "total_conflicts": self.world_state.total_conflicts,
            "total_births": self.world_state.total_births,
            "knowledge_stats": knowledge_stats,
            "expertise_stats": expertise_stats,
            "culture_stats": culture_stats,
            "innovation_stats": innovation_stats,
            "daily_results": daily_results,
            "agent_statuses": [a.status() for a in all_agents],
            "world_state": self.world_state.to_dict(),
        }

    def shutdown(self) -> None:
        for agent in self._agents.values():
            agent.shutdown()
