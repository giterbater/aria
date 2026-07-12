"""ARIA World — Village Simulation where ARIA-powered agents live, learn, and survive."""

from dataclasses import replace

from aria_core.environment.registry import register

from .models import ResourceType, ResourceInventory, AgentNeeds, Personality, Occupation, AgentState, WorldState, Family
from .config import SimulationConfig
from .agent import VillageAgent
from .world import WorldEngine
from .runner import SimulationRunner
from .dashboard import DashboardRenderer, render_dashboard, write_dashboard

SmallCityEnvironment = WorldEngine


def _small_city_factory(
    config: SimulationConfig | None = None,
    seed: int | None = None,
    **config_overrides,
) -> WorldEngine:
    env_config = replace(config, **config_overrides) if config is not None else SimulationConfig(**config_overrides)
    if seed is not None:
        env_config = replace(env_config, seed=seed)
    return WorldEngine(env_config)


def register_environment() -> None:
    register("SmallCity-v0", _small_city_factory, replace=True)


register_environment()

__all__ = [
    "ResourceType", "ResourceInventory", "AgentNeeds", "Personality",
    "Occupation", "AgentState", "WorldState", "Family",
    "SimulationConfig",
    "VillageAgent", "WorldEngine", "SmallCityEnvironment", "SimulationRunner",
    "DashboardRenderer", "render_dashboard", "write_dashboard",
    "register_environment",
]
