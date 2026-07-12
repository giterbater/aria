"""Tests for ARIA World civilization simulation."""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import random
import pytest

from aria_world.models import (
    ResourceType, ResourceInventory, AgentNeeds, Personality,
    Occupation, AgentState, WorldState, Family, RESOURCE_VALUES,
)
from aria_world.config import SimulationConfig
from aria_world.resources import ResourceSystem
from aria_world.needs import NeedsSystem
from aria_world.relationships import RelationshipGraph
from aria_world.occupations import OCCUPATIONS, FarmerHandler, BuilderHandler, HunterHandler
from aria_world.events import EventSystem, Event, EVENT_POOL
from aria_world.reproduction import ReproductionSystem
from aria_world.agent import VillageAgent, AgentDependencies
from aria_world.world import WorldEngine
from aria_world.metrics import SimulationMetrics
from aria_world.runner import SimulationRunner
from aria_world.knowledge_sharing import KnowledgeSharingSystem
from aria_world.expertise import ExpertiseSystem
from aria_world.culture import CultureSystem
from aria_world.innovation import InnovationSystem


# --- models.py tests ---

class TestResourceInventory:
    def test_add_and_has(self):
        inv = ResourceInventory()
        inv.add(ResourceType.WOOD, 5)
        assert inv.has(ResourceType.WOOD, 5)
        assert not inv.has(ResourceType.WOOD, 6)

    def test_remove(self):
        inv = ResourceInventory()
        inv.add(ResourceType.FOOD, 10)
        assert inv.remove(ResourceType.FOOD, 3)
        assert inv.resources[ResourceType.FOOD] == 7
        assert not inv.remove(ResourceType.FOOD, 10)

    def test_transfer(self):
        a = ResourceInventory()
        b = ResourceInventory()
        a.add(ResourceType.IRON, 5)
        assert a.transfer(b, ResourceType.IRON, 3)
        assert a.resources[ResourceType.IRON] == 2
        assert b.resources[ResourceType.IRON] == 3

    def test_total_value(self):
        inv = ResourceInventory()
        inv.add(ResourceType.FOOD, 10)
        inv.add(ResourceType.IRON, 5)
        assert inv.total_value() == 10 * 2.0 + 5 * 3.0

    def test_to_dict(self):
        inv = ResourceInventory()
        inv.add(ResourceType.WOOD, 3)
        d = inv.to_dict()
        assert d["wood"] == 3


class TestAgentNeeds:
    def test_most_urgent(self):
        needs = AgentNeeds(hunger=90, sleep=30, energy=80, safety=70, social=40)
        name, severity = needs.most_urgent()
        assert name == "hunger"
        assert severity > 0.8

    def test_overall_wellbeing(self):
        needs = AgentNeeds(hunger=0, sleep=0, energy=100, safety=100, social=0)
        assert needs.overall_wellbeing() == 1.0

    def test_is_dangerous(self):
        needs = AgentNeeds(hunger=100)
        assert needs.is_dangerous()

    def test_tick(self):
        rng = random.Random(42)
        needs = AgentNeeds(hunger=50, sleep=50, energy=80)
        needs.tick("farmer", 0, rng)
        assert needs.hunger > 50
        assert needs.sleep > 50
        assert needs.energy < 80


class TestPersonality:
    def test_to_cognitive_modifiers(self):
        p = Personality(aggression=0.8, diligence=0.9, curiosity=0.7)
        mods = p.to_cognitive_modifiers()
        assert "confidence" in mods
        assert "curiosity" in mods
        assert mods["curiosity"] > 0


class TestAgentState:
    def test_happiness(self):
        state = AgentState()
        state.needs.hunger = 0
        state.needs.sleep = 0
        state.needs.energy = 100
        state.needs.safety = 100
        state.needs.social = 0
        h = state.happiness()
        assert 0.5 <= h <= 1.0


# --- config.py tests ---

class TestSimulationConfig:
    def test_defaults(self):
        config = SimulationConfig()
        assert config.initial_agents == 10
        assert config.max_days == 100
        assert config.event_probability == 0.15


# --- resources.py tests ---

class TestResourceSystem:
    def test_initialize_world_resources(self):
        config = SimulationConfig()
        rs = ResourceSystem(config, random.Random(42))
        resources = rs.initialize_world_resources()
        assert ResourceType.WOOD in resources
        assert resources[ResourceType.WOOD] == 500

    def test_regen_world_resources(self):
        config = SimulationConfig()
        rs = ResourceSystem(config, random.Random(42))
        resources = rs.initialize_world_resources()
        old_wood = resources[ResourceType.WOOD]
        rs.regen_world_resources(resources)
        assert resources[ResourceType.WOOD] > old_wood

    def test_initialize_agent_inventory(self):
        config = SimulationConfig()
        rs = ResourceSystem(config, random.Random(42))
        inv = rs.initialize_agent_inventory(Occupation.FARMER)
        assert inv.has(ResourceType.FOOD, 1)


# --- needs.py tests ---

class TestNeedsSystem:
    def test_assess_needs(self):
        config = SimulationConfig()
        ns = NeedsSystem(config, random.Random(42))
        state = AgentState()
        state.needs.hunger = 80
        urgent = ns.assess_needs(state)
        assert len(urgent) > 0
        assert urgent[0]["need"] == "hunger"

    def test_derive_cognitive_needs(self):
        config = SimulationConfig()
        ns = NeedsSystem(config, random.Random(42))
        needs = AgentNeeds(hunger=80)
        mods = ns.derive_cognitive_needs(needs)
        assert "frustration" in mods

    def test_check_survival(self):
        config = SimulationConfig()
        ns = NeedsSystem(config, random.Random(42))
        state = AgentState()
        state.needs.hunger = 100
        assert not ns.check_survival(state)
        assert not state.alive


# --- relationships.py tests ---

class TestRelationshipGraph:
    def test_get_trust_default(self):
        rg = RelationshipGraph()
        assert rg.get_trust("a", "b") == 50.0

    def test_update_trust(self):
        rg = RelationshipGraph()
        rg.update_trust("a", "b", 20)
        assert rg.get_trust("a", "b") == 70.0

    def test_record_trade(self):
        rg = RelationshipGraph()
        rg.record_trade("a", "b", 10.0)
        assert rg.get_trust("a", "b") > 50.0

    def test_record_conflict(self):
        rg = RelationshipGraph()
        rg.record_conflict("a", "b")
        assert rg.get_trust("a", "b") < 50.0

    def test_average_trust(self):
        rg = RelationshipGraph()
        rg.initialize_pair("a", "b", 60.0)
        rg.initialize_pair("c", "d", 40.0)
        assert rg.average_trust() == 50.0


# --- occupations.py tests ---

class TestOccupations:
    def test_farmer_can_produce(self):
        handler = FarmerHandler()
        resources = {ResourceType.WATER: 10, ResourceType.WOOD: 10}
        assert handler.can_produce(resources)

    def test_farmer_produce(self):
        handler = FarmerHandler()
        resources = {ResourceType.WATER: 10}
        produced = handler.produce(resources, 0.5, random.Random(42))
        assert ResourceType.FOOD in produced
        assert produced[ResourceType.FOOD] > 0

    def test_builder_can_produce(self):
        handler = BuilderHandler()
        resources = {ResourceType.WOOD: 10, ResourceType.STONE: 10}
        assert handler.can_produce(resources)

    def test_hunter_can_always_produce(self):
        handler = HunterHandler()
        assert handler.can_produce({})

    def test_occupations_registry(self):
        assert len(OCCUPATIONS) == 5
        assert Occupation.FARMER in OCCUPATIONS


# --- events.py tests ---

class TestEventSystem:
    def test_event_pool_not_empty(self):
        assert len(EVENT_POOL) > 0

    def test_event_creation(self):
        event = Event(name="Test", description="Test event", effects={"food_loss": 10})
        assert event.name == "Test"

    def test_apply_event(self):
        config = SimulationConfig()
        es = EventSystem(config, random.Random(42))
        event = Event(name="Storm", description="A storm", effects={"food_loss": 20, "safety_drop": 10})
        state = AgentState()
        world = WorldState(resources={ResourceType.FOOD: 100})
        logs = es.apply_event(event, [state], world)
        assert world.resources[ResourceType.FOOD] == 80
        assert state.needs.safety == 60


# --- reproduction.py tests ---

class TestReproductionSystem:
    def test_create_child(self):
        config = SimulationConfig()
        rs = ReproductionSystem(config, random.Random(42))
        parent_a = AgentState(name="Alice", age=25, occupation=Occupation.FARMER)
        parent_a.inventory.add(ResourceType.FOOD, 10)
        parent_a.inventory.add(ResourceType.WATER, 10)
        parent_b = AgentState(name="Bob", age=30, occupation=Occupation.HUNTER)
        parent_b.inventory.add(ResourceType.FOOD, 10)
        parent_b.inventory.add(ResourceType.WATER, 10)
        child = rs.create_child(parent_a, parent_b, 1)
        assert child.age == 0
        assert child.parent_ids == [parent_a.id, parent_b.id]


# --- agent.py tests ---

class TestVillageAgent:
    def _make_deps(self, rng=None):
        rng = rng or random.Random(42)
        config = SimulationConfig()
        return AgentDependencies(
            resource_system=ResourceSystem(config, rng),
            needs_system=NeedsSystem(config, rng),
            relationship_graph=RelationshipGraph(),
            world_resources={ResourceType.WOOD: 100, ResourceType.STONE: 100, ResourceType.FOOD: 100, ResourceType.WATER: 100, ResourceType.IRON: 100},
            rng=rng,
            knowledge_sharing=KnowledgeSharingSystem(rng),
            expertise=ExpertiseSystem(rng),
            culture=CultureSystem(rng),
            innovation=InnovationSystem(rng),
        )

    def test_agent_creation(self):
        deps = self._make_deps()
        state = AgentState(name="Test", occupation=Occupation.FARMER)
        agent = VillageAgent(state, SimulationConfig(), deps)
        assert agent.is_alive()
        assert agent.state.name == "Test"

    def test_agent_status(self):
        deps = self._make_deps()
        state = AgentState(name="Test", occupation=Occupation.FARMER)
        agent = VillageAgent(state, SimulationConfig(), deps)
        status = agent.status()
        assert "name" in status
        assert "happiness" in status

    def test_agent_live_one_day(self):
        deps = self._make_deps()
        state = AgentState(name="Test", occupation=Occupation.FARMER)
        agent = VillageAgent(state, SimulationConfig(), deps)
        result = agent.live_one_day(1)
        assert "day" in result
        assert "alive" in result


# --- world.py tests ---

class TestWorldEngine:
    def test_world_initialization(self):
        config = SimulationConfig(initial_agents=5, seed=42)
        world = WorldEngine(config)
        world.initialize()
        assert len(world.get_alive_agents()) == 5

    def test_world_tick(self):
        config = SimulationConfig(initial_agents=5, seed=42)
        world = WorldEngine(config)
        world.initialize()
        result = world.tick()
        assert "day" in result
        assert result["day"] == 1

    def test_world_run(self):
        config = SimulationConfig(initial_agents=5, max_days=10, seed=42)
        world = WorldEngine(config)
        world.initialize()
        result = world.run()
        assert result["days_run"] > 0
        assert "survival_rate" in result
        world.shutdown()

    def test_world_resources_regen(self):
        config = SimulationConfig(initial_agents=5, seed=42)
        world = WorldEngine(config)
        world.initialize()
        old_food = world.world_state.resources.get(ResourceType.FOOD, 0)
        world.tick()
        assert world.world_state.resources.get(ResourceType.FOOD, 0) >= old_food
        world.shutdown()


# --- metrics.py tests ---

class TestSimulationMetrics:
    def test_from_simulation_result(self):
        result = {
            "seed": 42,
            "days_run": 50,
            "initial_population": 10,
            "final_population": 8,
            "survival_rate": 0.8,
            "average_happiness": 0.6,
            "average_lifespan_days": 40,
            "average_knowledge": 5.0,
            "total_trades": 20,
            "total_conflicts": 5,
            "total_births": 3,
        }
        metrics = SimulationMetrics.from_simulation_result(result)
        assert metrics.survival_rate == 0.8
        assert metrics.average_happiness == 0.6

    def test_to_metric_set(self):
        metrics = SimulationMetrics(
            survival_rate=0.8,
            average_happiness=0.6,
            average_knowledge=5.0,
            trade_volume=0.4,
            village_growth=1.2,
        )
        ms = metrics.to_metric_set(run_id="test", timestamp="2026-01-01")
        assert ms.get("simulation_survival_rate") == 0.8


# --- runner.py tests ---

class TestSimulationRunner:
    def test_runner_run(self):
        config = SimulationConfig(initial_agents=5, max_days=10, seed=42)
        runner = SimulationRunner(config)
        result = runner.run(days=10, seed=42)
        assert result["days_run"] > 0
        assert "survival_rate" in result

    def test_runner_benchmark(self):
        config = SimulationConfig(initial_agents=5, max_days=10, seed=42)
        runner = SimulationRunner(config)
        result = runner.benchmark(days=10, seed=42)
        assert "simulation_result" in result
        assert "metrics" in result
        assert "benchmark_results" in result
        assert len(result["benchmark_results"]) > 0

    def test_dashboard_renderer(self):
        from aria_world.dashboard import DashboardRenderer

        config = SimulationConfig(initial_agents=5, max_days=5, seed=42)
        runner = SimulationRunner(config)
        benchmark = runner.benchmark(days=5, seed=42)
        html = DashboardRenderer(benchmark["simulation_result"], benchmark).render_html()

        assert "ARIA World Dashboard" in html
        assert "World Map" in html
        assert "Trust Network" in html
        assert "Knowledge Graph" in html
        assert "Benchmark Scores" in html
        assert "simulation_survival_rate" in html


# --- Integration tests ---

class TestIntegration:
    def test_full_simulation(self):
        config = SimulationConfig(initial_agents=8, max_days=30, seed=42)
        runner = SimulationRunner(config)
        result = runner.run(days=30, seed=42)
        assert result["days_run"] > 0
        assert result["initial_population"] == 8
        assert result["final_population"] >= 1
        assert result["survival_rate"] > 0

    def test_deterministic(self):
        config1 = SimulationConfig(initial_agents=5, max_days=10, seed=42)
        config2 = SimulationConfig(initial_agents=5, max_days=10, seed=42)
        r1 = SimulationRunner(config1).run(days=10, seed=42)
        r2 = SimulationRunner(config2).run(days=10, seed=42)
        assert r1["survival_rate"] == r2["survival_rate"]
        assert r1["final_population"] == r2["final_population"]

    def test_reproduction(self):
        config = SimulationConfig(initial_agents=10, max_days=100, seed=42, reproduction_chance=0.3)
        runner = SimulationRunner(config)
        result = runner.run(days=100, seed=42)
        assert result.get("total_births", 0) >= 0

    def test_benchmark_integration(self):
        config = SimulationConfig(initial_agents=5, max_days=10, seed=42)
        runner = SimulationRunner(config)
        result = runner.benchmark(days=10, seed=42)
        assert len(result["benchmark_results"]) >= 5
        for br in result["benchmark_results"]:
            assert 0.0 <= br.score <= 1.0
