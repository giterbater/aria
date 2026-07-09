# Perception Architecture

## Research Question

**Can ARIA maintain identical cognition while operating in different worlds?**

Current: ARIA World (simulation)
Future: Google Earth, Maps, Wi-Fi, GPS, Camera, Internet, Robot sensors

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

## Architecture

```
aria_core/perception/
├── models.py           # Typed perception models
├── interfaces.py       # World Interface protocol
├── fusion.py           # Sensor fusion
├── memory.py           # Perception memory
├── context_builder.py  # Reasoning context builder
└── adapters/
    ├── simulation.py   # ARIA World adapter
    ├── gps.py          # GPS adapter
    ├── wifi.py         # Wi-Fi context adapter
    └── mock.py         # Testing adapter
```

---

## Typed Models

Every environment exposes identical information through these models:

### PerceptionFrame

The universal interface. Every adapter produces `PerceptionFrame` objects.

```python
@dataclass
class PerceptionFrame:
    timestamp: datetime
    source: str                    # "simulation", "gps", "wifi", etc.
    environment_type: EnvironmentType
    location: GeoLocation
    objects: list[PerceivedObject]
    agents: list[PerceivedAgent]
    resources: list[PerceivedResource]
    weather: PerceivedWeather
    terrain: PerceivedTerrain
    events: list[PerceivedEvent]
    overall_confidence: float
    completeness: float
```

### PerceptionContext

Processed perception ready for reasoning.

```python
@dataclass
class PerceptionContext:
    current_location: GeoLocation
    environment_type: EnvironmentType
    known_environment: bool
    nearby_agents: list[PerceivedAgent]
    nearby_resources: list[PerceivedResource]
    weather: PerceivedWeather
    terrain: PerceivedTerrain
    visited_locations: list[GeoLocation]
    known_wifi_networks: list[str]
    overall_confidence: float
```

---

## World Interface Protocol

Every adapter implements this protocol:

```python
class WorldInterface(Protocol):
    def get_current_perception(self) -> PerceptionFrame: ...
    def get_location(self) -> Optional[GeoLocation]: ...
    def is_available(self) -> bool: ...
    def get_confidence(self) -> float: ...
    def get_source_name(self) -> str: ...
```

---

## Adapters

### SimulationAdapter

Wraps ARIA World into the World Interface.

```python
adapter = SimulationAdapter(world_engine)
frame = adapter.get_current_perception()
# frame contains agents, resources, terrain from simulation
```

### GPSAdapter

Provides location from GPS sensor.

```python
adapter = GPSAdapter()
adapter.update_location(latitude=37.7749, longitude=-122.4194, accuracy=5.0)
frame = adapter.get_current_perception()
# frame contains GPS location
```

### WiFiAdapter

Detects environment context from Wi-Fi networks.

```python
adapter = WiFiAdapter()
adapter.add_known_network("HomeWiFi", "home")
adapter.update_scan([{"name": "HomeWiFi", "signal": -50}])
frame = adapter.get_current_perception()
# frame contains "likely at home" context
```

### MockAdapter

Configurable mock for testing.

```python
adapter = MockAdapter()
adapter.set_location(37.7749, -122.4194)
adapter.add_agent("Alice")
adapter.add_resource(ResourceType.FOOD, 10.0)
frame = adapter.get_current_perception()
```

---

## Sensor Fusion

Combines multiple perception sources into one frame.

```python
fusion = SimpleSensorFusion()
fusion.add_source(gps_adapter)
fusion.add_source(wifi_adapter)
fusion.add_source(mock_adapter)

fused_frame = fusion.fuse()
# fused_frame combines data from all sources
```

---

## Perception Memory

Stores observation history for episodic retrieval.

```python
memory = SimplePerceptionMemory()
memory.store(frame)

visited = memory.get_visited_locations()
known_wifi = memory.get_known_wifi_networks()
frequent = memory.get_frequently_visited()
```

---

## Context Builder

Enriches perception with memory for reasoning.

```python
builder = SimpleContextBuilder(memory)
context = builder.build_context(frame)
# context includes known_environment, nearby_known_places, etc.
```

---

## Wi-Fi Context Research

### Hypothesis

Wi-Fi networks can provide environmental context:
- Known networks → "likely at home/work"
- Signal strength → proximity estimate
- Network history → location familiarity

### Implementation

```python
adapter = WiFiAdapter()
adapter.add_known_network("HomeNetwork", "home")
adapter.add_known_network("OfficeWiFi", "office")

# Scan networks
adapter.update_scan([
    {"name": "HomeNetwork", "signal": -45},  # Strong signal
    {"name": "Unknown", "signal": -80},      # Weak signal
])

frame = adapter.get_current_perception()
# frame indicates "likely at home" with high confidence
```

### Research Questions

1. Can Wi-Fi networks reliably identify environments?
2. How does signal strength correlate with location accuracy?
3. Can Wi-Fi history improve spatial memory?

---

## Integration with Reasoning

Reasoning automatically consumes perception context:

```python
# Build perception
fusion = SimpleSensorFusion()
fusion.add_source(gps_adapter)
fusion.add_source(wifi_adapter)
frame = fusion.fuse()

# Build context
builder = SimpleContextBuilder(memory)
context = builder.build_context(frame)

# Convert to reasoning context
reasoning_context = context.to_reasoning_context()

# Reasoning uses this context
plan = reasoning_engine.reason(objective, reasoning_context)
```

---

## Benchmark Metrics

| Metric | Description |
|--------|-------------|
| Navigation accuracy | How accurately location is estimated |
| Environment recognition | How often environment is correctly identified |
| Context prediction | How well context predicts next state |
| Memory retrieval | How well past observations are retrieved |
| Planning improvement | How perception improves planning |
| Decision latency | Time from perception to decision |
| Adapter performance | Time per adapter call |
| Cross-environment consistency | Same cognition across different worlds |

---

## Future Work

1. **Google Earth Adapter** — Virtual environment perception
2. **Camera Adapter** — Visual perception
3. **Internet Adapter** — Web-based context
4. **Robot Adapter** — Physical sensor integration
5. **Geospatial Reasoning** — Navigation, spatial memory
6. **Place Recognition** — Landmark detection
7. **Route Planning** — Path optimization

---

*Generated: 2026-07-05*
