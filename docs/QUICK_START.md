# Quick Start

## Generate The ARIA World Dashboard

```powershell
python run_dashboard.py --days 60 --agents 12 --seed 42
```

Open:

```text
docs/screenshots/world_dashboard.html
```

## Run A Short Simulation In The Terminal

```powershell
python run_demo.py
```

## Run The 100-Day Report

```powershell
python run_100day.py
```

## Run Tests

```powershell
python -m pytest tests/test_aria_world.py tests/test_benchmark_framework.py -q
```

## Run Text Mode ARIA

```powershell
python -m text_mode_loop
```
