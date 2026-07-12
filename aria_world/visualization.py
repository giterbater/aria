"""Visualization module for ARIA World simulation.

Generates ASCII-based charts and graphs for terminal output.
Shows emergent behavior over time.
"""

from __future__ import annotations

import math
from typing import Any


BAR_FULL = "█"
BAR_HALF = "▓"
BAR_EMPTY = "░"
DOT = "●"
ARROW = "→"
HEART = "♥"
STAR = "★"
SKULL = "☠"
BABY = "⊕"
KNOWLEDGE = "◆"
TOOL = "⚙"
HOUSE = "□"


def _bar(value: float, max_val: float, width: int = 20, fill: str = BAR_FULL, empty: str = BAR_EMPTY) -> str:
    if max_val <= 0:
        return empty * width
    filled = int((value / max_val) * width)
    filled = max(0, min(width, filled))
    return fill * filled + empty * (width - filled)


def _sparkline(values: list[float], width: int = 40) -> str:
    if not values:
        return ""
    blocks = " ▁▂▃▄▅▆▇█"
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1
    step = max(1, len(values) // width)
    sampled = values[::step][:width]
    return "".join(blocks[min(len(blocks) - 1, int((v - mn) / rng * (len(blocks) - 1)))] for v in sampled)


def _mini_graph(values: list[float], width: int = 50, height: int = 10) -> str:
    if not values:
        return ""
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1
    step = max(1, len(values) // width)
    sampled = values[::step][:width]
    lines = []
    for row in range(height, -1, -1):
        threshold = mn + (rng * row / height)
        line = ""
        for v in sampled:
            if v >= threshold:
                line += "█"
            else:
                line += " "
        lines.append(line)
    return "\n".join(lines)


class SimulationVisualizer:
    """Generates visual reports from simulation results."""

    def __init__(self, result: dict) -> None:
        self.result = result
        self.daily = result.get("daily_results", [])
        self.width = 70

    def header(self, title: str) -> str:
        return f"\n{'=' * self.width}\n  {title}\n{'=' * self.width}"

    def population_over_time(self) -> str:
        if not self.daily:
            return "No daily data available."
        alive_counts = [d.get("alive_count", 0) for d in self.daily]
        births = [d.get("births", 0) for d in self.daily]
        deaths = [d.get("deaths", 0) for d in self.daily]

        max_pop = max(alive_counts) if alive_counts else 1
        lines = [self.header("Population Over Time"), ""]

        for i, count in enumerate(alive_counts):
            day = i + 1
            bar = _bar(count, max_pop, width=40)
            markers = ""
            if births[i] > 0:
                markers += f" {BABY}x{births[i]}"
            if deaths[i] > 0:
                markers += f" {SKULL}x{deaths[i]}"
            lines.append(f"Day {day:3d} |{bar}| {count}{markers}")

        lines.append("")
        lines.append(f"Population: {alive_counts[0] if alive_counts else 0} → {alive_counts[-1] if alive_counts else 0}")
        lines.append(f"Births: {sum(births)}  Deaths: {sum(deaths)}")
        return "\n".join(lines)

    def trust_network(self) -> str:
        rg = None
        for key in ["relationship_graph", "world_state"]:
            if key in self.result:
                break

        lines = [self.header("Trust Network"), ""]
        agents = self.result.get("agent_statuses", [])
        if not agents:
            return "No agent data."

        lines.append(f"  {'Agent':<12} {'Age':>4} {'Trust Network'}")
        lines.append(f"  {'─' * 12} {'─' * 4} {'─' * 40}")

        for agent in agents[:10]:
            name = agent.get("name", "?")[:12]
            age = agent.get("age", 0)
            trust_bar = _bar(agent.get("social", 50), 100, width=30)
            lines.append(f"  {name:<12} {age:>4.0f} |{trust_bar}| {agent.get('social', 0):.0f}")

        return "\n".join(lines)

    def knowledge_graph(self) -> str:
        ks = self.result.get("knowledge_stats", {})
        es = self.result.get("expertise_stats", {})

        lines = [self.header("Knowledge Graph"), ""]

        by_skill = ks.get("by_skill", {})
        if by_skill:
            lines.append("  Knowledge Distribution:")
            lines.append(f"  {'Skill':<15} {'Count':>6} {'Avg Level':>10} {'Visual'}")
            lines.append(f"  {'─' * 15} {'─' * 6} {'─' * 10} {'─' * 30}")
            for skill, stats in sorted(by_skill.items()):
                count = stats.get("count", 0)
                avg = stats.get("avg_level", 0)
                bar = _bar(avg, 1.0, width=25)
                lines.append(f"  {skill:<15} {count:>6} {avg:>10.2f} |{bar}|")
        else:
            lines.append("  No knowledge data yet.")

        lines.append("")
        expert_by_skill = es.get("by_skill", {})
        if expert_by_skill:
            lines.append("  Expertise Levels:")
            for skill, stats in sorted(expert_by_skill.items()):
                count = stats.get("count", 0)
                avg = stats.get("avg_level", 0)
                title = "Master" if avg >= 0.9 else "Expert" if avg >= 0.7 else "Journeyman" if avg >= 0.5 else "Apprentice" if avg >= 0.3 else "Novice"
                bar = _bar(avg, 1.0, width=30, fill=STAR, empty=BAR_EMPTY)
                lines.append(f"  {skill:<15} {bar} {avg:.2f} ({title})")

        lines.append("")
        lines.append(f"  Total Knowledge: {ks.get('total', 0)} entries")
        lines.append(f"  Average Level: {ks.get('average_level', 0):.2f}")
        lines.append(f"  Expert Agents: {es.get('experts', 0)}")
        lines.append(f"  Total Teachings: {ks.get('total_teachings', 0)} ({ks.get('successful_teachings', 0)} successful)")

        return "\n".join(lines)

    def innovation_graph(self) -> str:
        is_ = self.result.get("innovation_stats", {})
        lines = [self.header("Innovation & Technology"), ""]

        lines.append(f"  Recipes Discovered: {is_.get('total_recipes', 0)}")
        lines.append(f"  Innovations Made: {is_.get('total_innovations', 0)}")
        lines.append(f"  Recipes Used: {is_.get('recipes_used', 0)}")
        lines.append(f"  Avg Efficiency: {is_.get('average_efficiency', 0):.2f}")

        lines.append("")
        lines.append("  Technology Progress:")
        tech_score = min(1.0, is_.get("total_recipes", 3) / 10.0)
        bar = _bar(tech_score, 1.0, width=40)
        lines.append(f"  {bar} {tech_score:.0%}")

        return "\n".join(lines)

    def culture_spread(self) -> str:
        cs = self.result.get("culture_stats", {})
        lines = [self.header("Culture & Customs"), ""]

        lines.append(f"  Total Customs: {cs.get('total_customs', 0)}")
        lines.append(f"  Active Customs: {cs.get('active_customs', 0)}")
        lines.append(f"  Strong Customs: {cs.get('strong_customs', 0)}")
        lines.append(f"  Proven Strategies: {cs.get('proven_strategies', 0)}")
        lines.append(f"  Village Knowledge: {cs.get('village_knowledge_count', 0)}")

        adherence = cs.get("average_adherence", 0)
        lines.append("")
        lines.append("  Cultural Cohesion:")
        bar = _bar(adherence, 1.0, width=40)
        lines.append(f"  {bar} {adherence:.0%}")

        return "\n".join(lines)

    def happiness_sparkline(self) -> str:
        if not self.daily:
            return ""
        values = []
        for d in self.daily:
            agents = d.get("agent_statuses", [])
            if agents:
                avg = sum(a.get("happiness", 0.5) for a in agents) / len(agents)
                values.append(avg)
            else:
                values.append(0.5)

        lines = [self.header("Happiness Over Time"), ""]
        spark = _sparkline(values, width=50)
        lines.append(f"  {spark}")
        lines.append(f"  Min: {min(values):.2f}  Max: {max(values):.2f}  Avg: {sum(values)/len(values):.2f}")
        return "\n".join(lines)

    def resource_levels(self) -> str:
        ws = self.result.get("world_state", {})
        resources = ws.get("resources", {})
        if not resources:
            return ""

        lines = [self.header("Resource Levels"), ""]
        max_res = max(resources.values()) if resources else 1
        for res, qty in sorted(resources.items()):
            bar = _bar(qty, max_res, width=40)
            lines.append(f"  {res:<10} |{bar}| {qty:.0f}")
        return "\n".join(lines)

    def daily_events(self) -> str:
        events = []
        for d in self.daily:
            day_events = d.get("events", [])
            for e in day_events:
                events.append(f"Day {d.get('day', '?')}: {e}")
            conflicts = d.get("conflict_logs", [])
            for c in conflicts:
                events.append(c)

        if not events:
            return ""

        lines = [self.header("Notable Events"), ""]
        for e in events[-20:]:
            lines.append(f"  {e}")
        return "\n".join(lines)

    def summary_card(self) -> str:
        lines = [self.header("Simulation Summary"), ""]

        init = self.result.get("initial_population", 0)
        final = self.result.get("final_population", 0)
        days = self.result.get("days_run", 0)
        survival = self.result.get("survival_rate", 0)
        happiness = self.result.get("average_happiness", 0)
        knowledge = self.result.get("average_knowledge", 0)
        births = self.result.get("total_births", 0)
        conflicts = self.result.get("total_conflicts", 0)

        lines.append(f"  Duration: {days} days")
        lines.append(f"  Population: {init} → {final} ({'↑' if final > init else '↓'}{abs(final - init)})")
        lines.append(f"  Survival Rate: {survival:.0%}")
        lines.append(f"  Average Happiness: {happiness:.2f}")
        lines.append(f"  Average Knowledge: {knowledge:.1f}")
        lines.append(f"  Births: {births}")
        lines.append(f"  Conflicts: {conflicts}")

        ks = self.result.get("knowledge_stats", {})
        es = self.result.get("expertise_stats", {})
        is_ = self.result.get("innovation_stats", {})
        cs = self.result.get("culture_stats", {})

        lines.append("")
        lines.append(f"  Knowledge Entries: {ks.get('total', 0)}")
        lines.append(f"  Expert Agents: {es.get('experts', 0)}")
        lines.append(f"  Recipes: {is_.get('total_recipes', 0)}")
        lines.append(f"  Teachings: {ks.get('total_teachings', 0)} ({ks.get('successful_teachings', 0)} successful)")

        return "\n".join(lines)

    def full_report(self) -> str:
        sections = [
            self.summary_card(),
            self.population_over_time(),
            self.knowledge_graph(),
            self.innovation_graph(),
            self.culture_spread(),
            self.happiness_sparkline(),
            self.resource_levels(),
            self.daily_events(),
        ]
        return "\n\n".join(s for s in sections if s)
