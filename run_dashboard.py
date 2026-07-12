"""Generate the ARIA World HTML dashboard."""

from __future__ import annotations

import argparse
from pathlib import Path

from aria_world.config import SimulationConfig
from aria_world.dashboard import DashboardRenderer
from aria_world.runner import SimulationRunner


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an ARIA World dashboard HTML file.")
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--agents", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="docs/screenshots/world_dashboard.html")
    args = parser.parse_args()

    config = SimulationConfig(seed=args.seed, initial_agents=args.agents, max_days=args.days)
    runner = SimulationRunner(config)
    benchmark = runner.benchmark(days=args.days, seed=args.seed)
    result = benchmark["simulation_result"]
    target = DashboardRenderer(result, benchmark).write(args.out)
    print(f"Wrote dashboard: {Path(target).resolve()}")


if __name__ == "__main__":
    main()
