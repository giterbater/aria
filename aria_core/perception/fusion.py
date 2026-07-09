# aria_core/perception/fusion.py
"""
Sensor Fusion — combines multiple perception sources into one frame.

Takes multiple WorldInterface instances and produces a single
fused PerceptionFrame. Resolves conflicts and combines data.
"""

from __future__ import annotations

import datetime
from typing import Optional

from .models import (
    PerceptionFrame,
    GeoLocation,
    EnvironmentType,
)
from .interfaces import WorldInterface


class SimpleSensorFusion:
    """
    Combines multiple perception sources into one frame.
    
    Usage:
        fusion = SimpleSensorFusion()
        fusion.add_source(gps_adapter)
        fusion.add_source(wifi_adapter)
        fusion.add_source(mock_adapter)
        
        fused_frame = fusion.fuse()
    """
    
    def __init__(self):
        self._sources: list[WorldInterface] = []
    
    def add_source(self, source: WorldInterface) -> None:
        """Add a perception source."""
        if source not in self._sources:
            self._sources.append(source)
    
    def remove_source(self, source: WorldInterface) -> None:
        """Remove a perception source."""
        if source in self._sources:
            self._sources.remove(source)
    
    def fuse(self) -> PerceptionFrame:
        """
        Fuse all sources into a single PerceptionFrame.
        
        Strategy:
        1. Collect frames from all available sources
        2. Merge frames (later sources override earlier ones for conflicts)
        3. Combine unique entities
        4. Calculate overall confidence
        """
        frames = []
        
        # Collect frames from available sources
        for source in self._sources:
            if source.is_available():
                try:
                    frame = source.get_current_perception()
                    frames.append(frame)
                except Exception:
                    continue
        
        if not frames:
            return PerceptionFrame(
                source="fusion",
                environment_type=EnvironmentType.UNKNOWN,
                overall_confidence=0.0,
                completeness=0.0,
            )
        
        # Start with first frame
        result = frames[0]
        
        # Merge remaining frames
        for frame in frames[1:]:
            result = self._merge_frames(result, frame)
        
        # Update metadata
        result.source = "+".join(f.source for f in frames)
        result.timestamp = datetime.datetime.now()
        
        return result
    
    def get_confidence(self) -> float:
        """Get confidence in fused perception."""
        available = [s for s in self._sources if s.is_available()]
        if not available:
            return 0.0
        
        confidences = [s.get_confidence() for s in available]
        return sum(confidences) / len(confidences)
    
    def get_source_count(self) -> int:
        """Get number of available sources."""
        return sum(1 for s in self._sources if s.is_available())
    
    def _merge_frames(self, base: PerceptionFrame, override: PerceptionFrame) -> PerceptionFrame:
        """Merge two frames, with override taking precedence for conflicts."""
        
        # Location: use more accurate one
        location = base.location
        if override.location:
            if location is None or override.location.accuracy > location.accuracy:
                location = override.location
        
        # Environment type: use non-unknown
        env_type = base.environment_type
        if env_type == EnvironmentType.UNKNOWN and override.environment_type != EnvironmentType.UNKNOWN:
            env_type = override.environment_type
        
        # Combine entities (avoid duplicates by ID)
        objects = base.objects.copy()
        seen_ids = {o.id for o in objects}
        for obj in override.objects:
            if obj.id not in seen_ids:
                objects.append(obj)
                seen_ids.add(obj.id)
        
        agents = base.agents.copy()
        seen_ids = {a.id for a in agents}
        for agent in override.agents:
            if agent.id not in seen_ids:
                agents.append(agent)
                seen_ids.add(agent.id)
        
        resources = base.resources.copy()
        # Resources don't have IDs, so just combine
        resources.extend(override.resources)
        
        # Weather: use override if available
        weather = override.weather or base.weather
        
        # Terrain: use override if available
        terrain = override.terrain or base.terrain
        
        # Events: combine all
        events = base.events + override.events
        
        # Confidence: average
        confidence = (base.overall_confidence + override.overall_confidence) / 2
        
        # Completeness: combine
        completeness = min(1.0, base.completeness + override.completeness)
        
        return PerceptionFrame(
            timestamp=max(base.timestamp, override.timestamp),
            source="fusion",
            environment_type=env_type,
            location=location,
            objects=objects,
            agents=agents,
            resources=resources,
            weather=weather,
            terrain=terrain,
            events=events,
            overall_confidence=confidence,
            completeness=completeness,
        )
