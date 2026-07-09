# aria_core/perception/context_builder.py
"""
Context Builder — enriches perception with memory for reasoning.

Converts raw PerceptionFrame into PerceptionContext that
reasoning can consume. Adds:
- Known environment detection
- Frequently visited places
- Historical confidence
- Spatial memory
"""

from __future__ import annotations

import datetime
from typing import Optional

from .models import (
    PerceptionFrame,
    PerceptionContext,
    GeoLocation,
    EnvironmentType,
)
from .memory import SimplePerceptionMemory


class SimpleContextBuilder:
    """
    Builds reasoning context from perception + memory.
    
    Usage:
        builder = SimpleContextBuilder(memory)
        context = builder.build_context(frame)
        # context is ready for reasoning
    """
    
    def __init__(self, memory: Optional[SimplePerceptionMemory] = None):
        self._memory = memory
    
    def build_context(self, frame: PerceptionFrame) -> PerceptionContext:
        """
        Build a PerceptionContext from a PerceptionFrame.
        
        Enriches raw perception with memory data.
        """
        context = PerceptionContext(
            current_location=frame.location,
            environment_type=frame.environment_type,
            nearby_agents=frame.agents,
            nearby_objects=frame.objects,
            nearby_resources=frame.resources,
            weather=frame.weather,
            terrain=frame.terrain,
            recent_events=frame.events,
            overall_confidence=frame.overall_confidence,
        )
        
        # Add memory-based enrichment
        if self._memory is not None:
            context = self._enrich_with_memory(context, frame)
        
        return context
    
    def _enrich_with_memory(
        self,
        context: PerceptionContext,
        frame: PerceptionFrame,
    ) -> PerceptionContext:
        """Enrich context with memory data."""
        
        # Check if environment is known (from Wi-Fi)
        network_name = frame.raw_data.get("network_name")
        if network_name and self._memory.is_known_environment(network_name):
            context.known_environment = True
            context.environment_confidence = 0.9
            
            # Get location from memory
            known_location = self._memory.get_wifi_location(network_name)
            if known_location:
                context.nearby_known_places.append(network_name)
        
        # Add visited locations
        context.visited_locations = self._memory.get_visited_locations()
        
        # Add known Wi-Fi networks
        context.known_wifi_networks = self._memory.get_known_wifi_networks()
        
        # Check if current location is frequently visited
        if frame.location:
            frequently_visited = self._memory.get_frequently_visited(limit=5)
            for freq_loc in frequently_visited:
                if self._locations_close(frame.location, freq_loc, threshold_km=0.1):
                    context.nearby_known_places.append("frequently_visited")
                    context.known_environment = True
                    context.environment_confidence = max(
                        context.environment_confidence,
                        0.8,
                    )
        
        return context
    
    def _locations_close(
        self,
        loc1: GeoLocation,
        loc2: GeoLocation,
        threshold_km: float = 0.1,
    ) -> bool:
        """Check if two locations are close."""
        import math
        
        R = 6371.0  # Earth radius in km
        
        lat1_rad = math.radians(loc1.latitude)
        lat2_rad = math.radians(loc2.latitude)
        dlat = math.radians(loc2.latitude - loc1.latitude)
        dlon = math.radians(loc2.longitude - loc1.longitude)
        
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        distance_km = R * c
        return distance_km <= threshold_km
