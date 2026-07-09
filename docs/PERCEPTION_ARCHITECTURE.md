# Perception Architecture

## Research Question

**Can ARIA maintain identical cognition while operating in different worlds?**

The cognition should remain unchanged. Only perception changes.

---

## Design Principle

**ARIA Core never knows where data came from.**

```
Simulation → Adapter → PerceptionFrame → ARIA Core
GPS → Adapter → PerceptionFrame → ARIA Core
Wi-Fi → Adapter → PerceptionFrame → ARIA Core
Camera → Adapter → PerceptionFrame → ARIA Core
```

ARIA Core consumes only `PerceptionFrame`. It doesn't know if the frame came from a simulation, a GPS sensor, or a camera.

---

## Adapter Levels

### Level 1: Functional

These adapters actually work with real data or real APIs.

| Adapter | Status | Source | What It Does |
|---------|--------|--------|--------------|
| MockAdapter | ✅ Functional | Test data | Configurable mock for testing |
| SimulationAdapter | ✅ Functional | ARIA World | Wraps existing simulation |
| GPSAdapter | ✅ Functional | GPS input | Accepts coordinates, produces frames |

### Level 2: Interface Only

These adapters define the interface but need real backends.

| Adapter | Status | Needs | What It Would Do |
|---------|--------|-------|------------------|
| WiFiAdapter | 🔲 Interface | WiFi scanning API | Detect environment from networks |
| GoogleEarthAdapter | 🔲 Interface | Earth data provider | Terrain, landmarks, satellite |
| CameraAdapter | 🔲 Interface | Vision provider | Object detection, scene classification |
| InternetAdapter | 🔲 Interface | Web APIs | IP location, weather, events |

### Level 3: Future

Not yet implemented. Listed for research direction.

- Robot Adapter (physical sensors)
- LIDAR Adapter (3D scanning)
- Audio Adapter (sound recognition)

---

## What's Real vs What's Interface

### MockAdapter — REAL

```python
# This actually works
adapter = MockAdapter()
adapter.set_location(37.7749, -122.4194)
adapter.add_agent("Alice", "human")
adapter.add_resource(ResourceType.FOOD, 10.0)
adapter.set_weather(WeatherCondition.CLEAR, 22.0)

frame = adapter.get_current_perception()
# frame contains real data you just set
```

### SimulationAdapter — REAL

```python
# This wraps ARIA World
from aria_world.world import WorldEngine
from aria_world.config import SimulationConfig

world = WorldEngine(SimulationConfig(seed=42))
world.initialize()

adapter = SimulationAdapter(world)
frame = adapter.get_current_perception()
# frame contains real simulation state
```

### GPSAdapter — REAL (accepts manual input)

```python
# This accepts GPS coordinates
adapter = GPSAdapter()
adapter.update_location(
    latitude=37.7749,
    longitude=-122.4194,
    accuracy=5.0
)

frame = adapter.get_current_perception()
# frame contains the coordinates you provided
# NOTE: Does NOT read from actual GPS hardware
# You must call update_location() manually
```

### WiFiAdapter — INTERFACE ONLY

```python
# This defines the interface
adapter = WiFiAdapter()
adapter.add_known_network("HomeWiFi", "home")

# But update_scan() needs a real WiFi scanning backend
# Currently you must call it manually:
adapter.update_scan([
    {"name": "HomeWiFi", "signal": -50}
])

# No actual WiFi scanning happens
```

### GoogleEarthAdapter — INTERFACE ONLY

```python
# This defines the interface
adapter = GoogleEarthAdapter()
adapter.set_location(37.7749, -122.4194)

# But terrain/landmark data needs a real Earth data provider
# Currently returns defaults
```

### CameraAdapter — INTERFACE ONLY

```python
# This defines the interface
adapter = CameraAdapter()

# But process_image() needs a real vision provider
# Currently returns empty detection
```

### InternetAdapter — INTERFACE ONLY

```python
# This defines the interface
adapter = InternetAdapter()

# But update_from_ip() needs a real web API
# Currently returns no data
```

---

## What's Actually Implemented

### Core Infrastructure (REAL)

- `PerceptionFrame` — typed model ✅
- `PerceptionContext` — reasoning context ✅
- `WorldInterface` — protocol ✅
- `SimpleSensorFusion` — combines sources ✅
- `SimplePerceptionMemory` — stores history ✅
- `SimpleContextBuilder` — enriches perception ✅
- `GeospatialReasoner` — distance, familiarity ✅

### Adapters

- `MockAdapter` — fully functional ✅
- `SimulationAdapter` — wraps ARIA World ✅
- `GPSAdapter` — accepts manual input ✅
- `WiFiAdapter` — interface defined, needs backend 🔲
- `GoogleEarthAdapter` — interface defined, needs backend 🔲
- `CameraAdapter` — interface defined, needs backend 🔲
- `InternetAdapter` — interface defined, needs backend 🔲

---

## Research Direction: Environment-Agnostic Cognition

The real contribution isn't specific adapters. It's the architecture:

```
Any Environment
      ↓
   Adapter
      ↓
PerceptionFrame
      ↓
  ARIA Core
      ↓
  Reasoning
      ↓
  Decisions
```

This means:
1. Add a new environment = write one adapter
2. Cognition never changes
3. All environments produce identical data types
4. Sensor fusion combines multiple sources

---

## What Would Make This Real

To move from interface to functional:

1. **GPS**: Connect to actual GPS hardware or NMEA parser
2. **WiFi**: Connect to `nmcli`, `iwlist`, or platform WiFi API
3. **Google Earth**: Connect to Google Earth API or similar
4. **Camera**: Connect to OpenCV, YOLO, or cloud vision API
5. **Internet**: Connect to weather API, IP geolocation, news API

Each adapter already defines the interface. The backend is pluggable.

---

## Tests

91 tests pass, covering:
- Perception models
- Adapter interfaces
- Sensor fusion
- Perception memory
- Context building
- Geospatial reasoning

---

*Generated: 2026-07-05*
*Status: Architecture + Level 1 adapters functional, Level 2 interfaces defined*
