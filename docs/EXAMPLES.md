# Examples

## Generate A Dashboard

```powershell
python run_dashboard.py --days 100 --agents 15 --seed 42 --out docs/screenshots/world_dashboard.html
```

The dashboard is a standalone HTML file. It can be opened directly in a browser or attached to a release.

## Run A Simulation Programmatically

```python
from aria_world.config import SimulationConfig
from aria_world.runner import SimulationRunner

config = SimulationConfig(seed=42, initial_agents=10, max_days=50)
runner = SimulationRunner(config)
result = runner.run(days=50, seed=42)

print(result["final_population"])
print(result["survival_rate"])
```

## Render Dashboard HTML Programmatically

```python
from aria_world.dashboard import write_dashboard

write_dashboard(result, "docs/screenshots/world_dashboard.html")
```

## Run Simulation Benchmarks

```python
from aria_world.config import SimulationConfig
from aria_world.runner import SimulationRunner

runner = SimulationRunner(SimulationConfig(seed=42, initial_agents=10, max_days=50))
benchmark = runner.benchmark(days=50, seed=42)

for item in benchmark["benchmark_results"]:
    print(item.task_name, item.score)
```
