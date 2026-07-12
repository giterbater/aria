"""VillageAgent — wraps ARIACore + CognitiveEngine for simulated villagers."""

from __future__ import annotations

import logging
import random as _random
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from aria_core.integration import ARIACore
from aria_core.goals import Goal
from aria_core.reasoning import ReasoningContext
from aria_core.cognitive.engine import CognitiveEngine
from aria_core.cognitive.state import InternalState
from aria_core.memory.models import EpisodicItem, WorkingMemoryItem, Outcome
from aria_core.reflection.interfaces import SkillOutcome

from .models import AgentState, ResourceType, Occupation
from .config import SimulationConfig
from .resources import ResourceSystem
from .needs import NeedsSystem
from .relationships import RelationshipGraph
from .occupations import OCCUPATIONS
from .skills import VILLAGE_SKILLS
from .knowledge_sharing import KnowledgeSharingSystem
from .expertise import ExpertiseSystem
from .culture import CultureSystem
from .innovation import InnovationSystem

if TYPE_CHECKING:
    from .world import WorldEngine

logger = logging.getLogger("aria_world.agent")


@dataclass
class AgentDependencies:
    resource_system: ResourceSystem
    needs_system: NeedsSystem
    relationship_graph: RelationshipGraph
    world_resources: dict  # reference to world resource pool
    rng: _random.Random
    knowledge_sharing: KnowledgeSharingSystem
    expertise: ExpertiseSystem
    culture: CultureSystem
    innovation: InnovationSystem


class VillageAgent:
    def __init__(
        self,
        state: AgentState,
        config: SimulationConfig,
        deps: AgentDependencies,
    ) -> None:
        self.state = state
        self.config = config
        self.deps = deps

        self.aria = ARIACore(llm=None, db_path=f":memory:")
        self.cognitive = CognitiveEngine(
            reasoning=self.aria.reasoning,
            db_path=f":memory:",
        )

        for skill_cls in VILLAGE_SKILLS:
            skill = skill_cls()
            self.aria.skills.register(skill)

    def live_one_day(self, day: int) -> dict:
        if not self.state.alive:
            return {"day": day, "alive": False, "agent": self.state.name}

        self.deps.needs_system.tick_needs(self.state)
        self.state.age += 1.0 / 365.0

        if not self.deps.needs_system.check_survival(self.state):
            return {"day": day, "alive": False, "agent": self.state.name, "cause": self.state.cause_of_death}

        urgent_needs = self.deps.needs_system.assess_needs(self.state)
        objective = self._build_objective(urgent_needs)

        self.aria.goals.add_goal(Goal(description=objective, priority=1.0))

        produced = self._do_work(day)
        social_interactions = self._do_social(day)

        self.deps.resource_system.consume_needs(self.state)
        self._consume_daily_needs()

        self._reflect_on_day(day, objective, produced)
        self._learn_from_experience()

        self.state.days_survived += 1

        return {
            "day": day,
            "alive": True,
            "agent": self.state.name,
            "occupation": self.state.occupation.value,
            "produced": produced,
            "happiness": self.state.happiness(),
            "hunger": self.state.needs.hunger,
            "energy": self.state.needs.energy,
        }

    def _build_objective(self, urgent_needs: list[dict]) -> str:
        if not urgent_needs:
            return f"Work as {self.state.occupation.value}"
        top = urgent_needs[0]
        need = top["need"]
        if need == "hunger":
            if self.state.inventory.has(ResourceType.FOOD, 1):
                return "eat food to reduce hunger"
            return f"produce food by {self.state.occupation.value}"
        if need == "sleep":
            return "rest to recover energy"
        if need == "energy":
            return "take a break to restore energy"
        if need == "safety":
            return "secure the area"
        if need == "social":
            return "socialize with other villagers"
        return f"work as {self.state.occupation.value}"

    def _do_work(self, day: int) -> dict[str, Any]:
        occ_handler = OCCUPATIONS.get(self.state.occupation)
        if not occ_handler:
            return {"produced": {}}

        if not occ_handler.can_produce(self.deps.world_resources):
            return {"produced": {}, "reason": "insufficient_world_resources"}

        produced = occ_handler.produce(
            self.deps.world_resources,
            self.state.personality.diligence,
            self.deps.rng,
        )

        skill_name = occ_handler.skill_name()
        multiplier = self.deps.expertise.get_production_multiplier(self.state.id, skill_name)
        for res, qty in produced.items():
            boosted = qty * multiplier
            self.state.inventory.add(res, boosted)
            self.state.money += boosted * 0.5
            produced[res] = boosted

        self.deps.expertise.record_practice(self.state.id, skill_name, success=True)
        self.deps.knowledge_sharing.improve_knowledge(self.state.id, skill_name, delta=0.03)

        energy_cost = occ_handler.daily_energy_cost()
        self.state.needs.energy = max(0, self.state.needs.energy - energy_cost)

        outcome = SkillOutcome(
            skill_name=occ_handler.skill_name(),
            action="daily_work",
            success=True,
            duration_ms=0,
            output=f"Produced: {produced}",
        )
        self.aria.reflection.reflect_skill(outcome)
        self.state.total_actions += 1

        return {"produced": {r.value: q for r, q in produced.items()}}

    def _do_social(self, day: int) -> int:
        interactions = 0
        all_trust = self.deps.relationship_graph.get_all_trust_for(self.state.id)

        if self.state.needs.social > 60 and all_trust:
            best_partner = max(all_trust, key=all_trust.get)
            self.deps.relationship_graph.record_socialize(self.state.id, best_partner, day)
            self.state.needs.social = max(0, self.state.needs.social - 15)
            interactions += 1

            if not self.config._disable_trust:
                trust_level = all_trust[best_partner]
                if trust_level > 40 and self.state.age > 20:
                    self.deps.knowledge_sharing.attempt_teaching(
                        self.state.id, best_partner, trust_level, day,
                    )

        if self.state.inventory.has(ResourceType.TOOLS, 1) and self.deps.rng.random() < 0.2:
            if all_trust:
                trade_partner = self.deps.rng.choice(list(all_trust.keys()))
                self._offer_trade(trade_partner, day)
                interactions += 1

        if not self.config._disable_curiosity:
            if self.state.personality.curiosity > 0.6 and self.deps.rng.random() < 0.1:
                skill_level = self.deps.expertise.get_profile(
                    self.state.id, self.state.occupation.value,
                ).level
                self.deps.innovation.attempt_discovery(
                    self.state.id, skill_level, day,
                    {r.value: q for r, q in self.state.inventory.resources.items()},
                )

        return interactions

    def _offer_trade(self, partner_id: str, day: int) -> None:
        inv = self.state.inventory
        if inv.has(ResourceType.TOOLS, 1):
            inv.remove(ResourceType.TOOLS, 1)
            self.state.money += 3.0
            self.deps.relationship_graph.record_trade(self.state.id, partner_id, 3.0, day)
            self.deps.world_resources[ResourceType.TOOLS] = self.deps.world_resources.get(ResourceType.TOOLS, 0) + 1

    def _consume_daily_needs(self) -> None:
        occ = OCCUPATIONS.get(self.state.occupation)
        if not occ:
            return
        food_cost = occ.daily_food_cost()
        water_cost = occ.daily_water_cost()
        if self.state.inventory.has(ResourceType.FOOD, food_cost):
            self.state.inventory.remove(ResourceType.FOOD, food_cost)
            self.state.needs.hunger = max(0, self.state.needs.hunger - 20)
        if self.state.inventory.has(ResourceType.WATER, water_cost):
            self.state.inventory.remove(ResourceType.WATER, water_cost)
            self.state.needs.sleep = max(0, self.state.needs.sleep - 10)

    def _reflect_on_day(self, day: int, objective: str, produced: dict) -> None:
        if self.config._disable_reflection:
            return

        success = bool(produced.get("produced"))
        result_str = "success" if produced.get("produced") else "limited production"
        self.aria.reflection.reflect(
            action=f"day_{day}: {objective}",
            result=result_str,
            context={"day": day, "objective": objective, "produced": produced},
        )
        self.state.total_reflections += 1

        if not self.config._disable_memory:
            episode = EpisodicItem(
                importance=0.6 if success else 0.4,
                structured_input={"objective": objective, "day": day},
                decision={"occupation": self.state.occupation.value},
                outcome=Outcome.SUCCESS.value if success else Outcome.PARTIAL.value,
                notes=str(produced),
            )
            self.aria.memory.store_episodic(episode)

    def _learn_from_experience(self) -> None:
        if self.config._disable_reflection:
            return

        self.aria.learning.learn_from_reflections()
        self.aria.learning.learn_from_skill_stats()
        self.state.knowledge_entries = self.aria.knowledge.count()

        expertise_profiles = self.deps.expertise.get_agent_profiles(self.state.id)
        for p in expertise_profiles:
            self.deps.knowledge_sharing.improve_knowledge(
                self.state.id, p.skill, delta=p.level * 0.01,
            )

        proven_strategies = self.deps.culture.get_proven_strategies()
        for s in proven_strategies:
            if self.state.age > 20 and self.deps.rng.random() < 0.3:
                self.deps.culture.reinforce_custom(s.name, benefit=0.05)

        cognitive_mods = self.state.personality.to_cognitive_modifiers()
        need_mods = self.deps.needs_system.derive_cognitive_needs(self.state.needs)
        all_mods = {**cognitive_mods, **need_mods}
        for key, delta in all_mods.items():
            if hasattr(self.cognitive.state, key):
                current = getattr(self.cognitive.state, key)
                new_val = max(0.0, min(1.0, current + delta * 0.1))
                setattr(self.cognitive.state, key, new_val)

    def is_alive(self) -> bool:
        return self.state.alive

    def happiness(self) -> float:
        return self.state.happiness()

    def status(self) -> dict:
        return {
            "name": self.state.name,
            "age": self.state.age,
            "alive": self.state.alive,
            "occupation": self.state.occupation.value,
            "happiness": self.state.happiness(),
            "hunger": self.state.needs.hunger,
            "energy": self.state.needs.energy,
            "social": self.state.needs.social,
            "money": self.state.money,
            "inventory": self.state.inventory.to_dict(),
            "knowledge": self.state.knowledge_entries,
            "days_survived": self.state.days_survived,
            "total_actions": self.state.total_actions,
        }

    def shutdown(self) -> None:
        try:
            self.aria.shutdown()
        except Exception:
            pass
