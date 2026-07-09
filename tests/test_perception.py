# tests/test_perception.py
"""
Tests for the perception layer.

Validates:
1. Perception models work correctly
2. Adapters produce valid frames
3. Sensor fusion combines sources
4. Memory stores and retrieves
5. Context builder enriches perception
"""

from __future__ import annotations

import pytest
import datetime

from aria_core.perception.models import (
    PerceptionFrame,
    PerceptionContext,
    GeoLocation,
    EnvironmentType,
    ObjectType,
    ResourceType,
    WeatherCondition,
    TerrainType,
    PerceivedAgent,
    PerceivedResource,
    PerceivedWeather,
)
from aria_core.perception.adapters.simulation import SimulationAdapter
from aria_core.perception.adapters.wifi import WiFiAdapter
from aria_core.perception.adapters.gps import GPSAdapter
from aria_core.perception.adapters.mock import MockAdapter
from aria_core.perception.fusion import SimpleSensorFusion
from aria_core.perception.memory import SimplePerceptionMemory
from aria_core.perception.context_builder import SimpleContextBuilder


class TestPerceptionModels:
    """Test perception data models."""

    def test_perception_frame_creation(self):
        """Test that PerceptionFrame can be created."""
        frame = PerceptionFrame()
        assert frame.frame_id
        assert frame.timestamp
        assert frame.source == "unknown"
        assert frame.environment_type == EnvironmentType.UNKNOWN

    def test_geolocation_creation(self):
        """Test that GeoLocation can be created."""
        loc = GeoLocation(latitude=37.7749, longitude=-122.4194)
        assert loc.latitude == 37.7749
        assert loc.longitude == -122.4194
        assert loc.source == "unknown"

    def test_perception_frame_merge(self):
        """Test that PerceptionFrame can be merged."""
        frame1 = PerceptionFrame(
            source="gps",
            location=GeoLocation(latitude=1.0, longitude=2.0),
            agents=[PerceivedAgent(name="Alice")],
        )
        
        frame2 = PerceptionFrame(
            source="wifi",
            location=GeoLocation(latitude=1.1, longitude=2.1, accuracy=0.9),
            agents=[PerceivedAgent(name="Bob")],
        )
        
        merged = frame1.merge(frame2)
        
        assert len(merged.agents) == 2
        assert merged.source == "gps+wifi"

    def test_perception_context_to_dict(self):
        """Test that PerceptionContext can be converted to dict."""
        context = PerceptionContext(
            current_location=GeoLocation(latitude=1.0, longitude=2.0),
            environment_type=EnvironmentType.INDOOR,
            known_environment=True,
        )
        
        d = context.to_reasoning_context()
        
        assert "location" in d
        assert "environment" in d
        assert d["environment"] == "indoor"
        assert d["location"]["known_environment"] is True


class TestAdapters:
    """Test environment adapters."""

    def test_mock_adapter(self):
        """Test MockAdapter produces valid frames."""
        adapter = MockAdapter()
        adapter.set_location(37.7749, -122.4194)
        adapter.add_agent("Alice", "human")
        adapter.add_resource(ResourceType.FOOD, 10.0)
        adapter.set_weather(WeatherCondition.CLEAR, 22.0)
        
        frame = adapter.get_current_perception()
        
        assert frame.location is not None
        assert len(frame.agents) == 1
        assert len(frame.resources) == 1
        assert frame.weather is not None
        assert frame.overall_confidence > 0

    def test_gps_adapter(self):
        """Test GPSAdapter produces valid frames."""
        adapter = GPSAdapter()
        adapter.update_location(37.7749, -122.4194, accuracy=5.0)
        
        frame = adapter.get_current_perception()
        
        assert frame.location is not None
        assert frame.location.latitude == 37.7749
        assert frame.source == "gps"

    def test_wifi_adapter(self):
        """Test WiFiAdapter produces valid frames."""
        adapter = WiFiAdapter()
        adapter.add_known_network("HomeWiFi", "home")
        adapter.update_scan([
            {"name": "HomeWiFi", "signal": -50},
            {"name": "Unknown", "signal": -70},
        ])
        
        frame = adapter.get_current_perception()
        
        assert frame.source == "wifi"
        assert adapter.is_known_environment()
        assert adapter.get_location_label() == "home"

    def test_wifi_adapter_unknown_network(self):
        """Test WiFiAdapter with unknown network."""
        adapter = WiFiAdapter()
        adapter.update_scan([
            {"name": "UnknownNetwork", "signal": -50},
        ])
        
        frame = adapter.get_current_perception()
        
        assert adapter.get_location_label() is None

    def test_simulation_adapter_no_world(self):
        """Test SimulationAdapter with no world."""
        adapter = SimulationAdapter(None)
        
        frame = adapter.get_current_perception()
        
        assert frame.overall_confidence == 0.0


class TestSensorFusion:
    """Test sensor fusion."""

    def test_fusion_combines_sources(self):
        """Test that fusion combines multiple sources."""
        fusion = SimpleSensorFusion()
        
        gps = GPSAdapter()
        gps.update_location(37.7749, -122.4194, accuracy=5.0)
        
        mock = MockAdapter()
        mock.add_agent("Alice")
        
        fusion.add_source(gps)
        fusion.add_source(mock)
        
        frame = fusion.fuse()
        
        assert frame.location is not None
        assert len(frame.agents) == 1

    def test_fusion_empty_sources(self):
        """Test fusion with no available sources."""
        fusion = SimpleSensorFusion()
        
        frame = fusion.fuse()
        
        assert frame.overall_confidence == 0.0

    def test_fusion_confidence(self):
        """Test fusion confidence calculation."""
        fusion = SimpleSensorFusion()
        
        gps = GPSAdapter()
        gps.update_location(37.7749, -122.4194, accuracy=5.0)
        
        fusion.add_source(gps)
        
        confidence = fusion.get_confidence()
        
        assert 0.0 < confidence <= 1.0


class TestPerceptionMemory:
    """Test perception memory."""

    def test_store_and_retrieve(self):
        """Test storing and retrieving frames."""
        memory = SimplePerceptionMemory()
        
        frame = PerceptionFrame(
            location=GeoLocation(latitude=37.7749, longitude=-122.4194),
            raw_data={"network_name": "HomeWiFi"},
        )
        
        memory.store(frame)
        
        assert memory.get_frame_count() == 1
        assert "HomeWiFi" in memory.get_known_wifi_networks()

    def test_frequently_visited(self):
        """Test frequently visited locations."""
        memory = SimplePerceptionMemory()
        
        # Store multiple frames at same location
        for _ in range(5):
            frame = PerceptionFrame(
                location=GeoLocation(latitude=37.7749, longitude=-122.4194),
            )
            memory.store(frame)
        
        # Store one frame at different location
        frame2 = PerceptionFrame(
            location=GeoLocation(latitude=37.7750, longitude=-122.4195),
        )
        memory.store(frame2)
        
        frequently_visited = memory.get_frequently_visited(limit=1)
        
        assert len(frequently_visited) == 1
        assert frequently_visited[0].latitude == 37.7749

    def test_wifi_location(self):
        """Test getting location from Wi-Fi network."""
        memory = SimplePerceptionMemory()
        
        frame = PerceptionFrame(
            location=GeoLocation(latitude=37.7749, longitude=-122.4194),
            raw_data={"network_name": "HomeWiFi"},
        )
        
        memory.store(frame)
        
        location = memory.get_wifi_location("HomeWiFi")
        
        assert location is not None
        assert location.latitude == 37.7749


class TestContextBuilder:
    """Test context builder."""

    def test_build_context(self):
        """Test building context from frame."""
        builder = SimpleContextBuilder()
        
        frame = PerceptionFrame(
            location=GeoLocation(latitude=37.7749, longitude=-122.4194),
            environment_type=EnvironmentType.INDOOR,
            agents=[PerceivedAgent(name="Alice")],
        )
        
        context = builder.build_context(frame)
        
        assert context.current_location is not None
        assert context.environment_type == EnvironmentType.INDOOR
        assert len(context.nearby_agents) == 1

    def test_build_context_with_memory(self):
        """Test building context with memory enrichment."""
        memory = SimplePerceptionMemory()
        builder = SimpleContextBuilder(memory)
        
        # Store a frame first
        frame1 = PerceptionFrame(
            location=GeoLocation(latitude=37.7749, longitude=-122.4194),
            raw_data={"network_name": "HomeWiFi"},
        )
        memory.store(frame1)
        
        # Build context for new frame at same location
        frame2 = PerceptionFrame(
            location=GeoLocation(latitude=37.7749, longitude=-122.4194),
            raw_data={"network_name": "HomeWiFi"},
        )
        
        context = builder.build_context(frame2)
        
        assert context.known_environment is True
        assert "HomeWiFi" in context.known_wifi_networks


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
