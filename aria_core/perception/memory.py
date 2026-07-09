# aria_core/perception/memory.py
"""
Perception Memory — stores observation history for episodic retrieval.

Stores:
- Visited locations
- Known Wi-Fi networks
- Frequently visited places
- Observed landmarks
- Environmental changes
- Confidence history

Allows episodic retrieval for reasoning.
"""

from __future__ import annotations

import datetime
import math
from typing import Optional

from .models import PerceptionFrame, GeoLocation


class SimplePerceptionMemory:
    """
    In-memory storage for perception history.
    
    Usage:
        memory = SimplePerceptionMemory()
        memory.store(frame)
        
        visited = memory.get_visited_locations()
        known_wifi = memory.get_known_wifi_networks()
    """
    
    def __init__(self, max_frames: int = 1000):
        self._frames: list[PerceptionFrame] = []
        self._max_frames = max_frames
        self._known_wifi: dict[str, int] = {}  # name -> count
        self._visited_locations: list[GeoLocation] = []
        self._location_counts: dict[str, int] = {}  # "lat,lon" -> count
    
    def store(self, frame: PerceptionFrame) -> None:
        """Store a perception frame."""
        self._frames.append(frame)
        
        # Trim old frames
        if len(self._frames) > self._max_frames:
            self._frames = self._frames[-self._max_frames:]
        
        # Update Wi-Fi networks
        if frame.raw_data.get("network_name"):
            net_name = frame.raw_data["network_name"]
            self._known_wifi[net_name] = self._known_wifi.get(net_name, 0) + 1
        
        # Update visited locations
        if frame.location:
            self._visited_locations.append(frame.location)
            loc_key = f"{frame.location.latitude:.4f},{frame.location.longitude:.4f}"
            self._location_counts[loc_key] = self._location_counts.get(loc_key, 0) + 1
    
    def get_recent(self, limit: int = 10) -> list[PerceptionFrame]:
        """Get recent perception frames."""
        return self._frames[-limit:]
    
    def get_by_location(
        self,
        location: GeoLocation,
        radius_km: float = 1.0,
    ) -> list[PerceptionFrame]:
        """Get perception frames near a location."""
        result = []
        for frame in self._frames:
            if frame.location:
                dist = self._haversine_km(
                    location.latitude, location.longitude,
                    frame.location.latitude, frame.location.longitude,
                )
                if dist <= radius_km:
                    result.append(frame)
        return result
    
    def get_known_wifi_networks(self) -> list[str]:
        """Get list of known Wi-Fi network names."""
        return list(self._known_wifi.keys())
    
    def get_visited_locations(self) -> list[GeoLocation]:
        """Get list of visited locations."""
        return self._visited_locations.copy()
    
    def get_frequently_visited(self, limit: int = 10) -> list[GeoLocation]:
        """Get most frequently visited locations."""
        # Sort by count
        sorted_locs = sorted(
            self._location_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        
        result = []
        for loc_key, count in sorted_locs[:limit]:
            lat, lon = map(float, loc_key.split(","))
            result.append(GeoLocation(
                latitude=lat,
                longitude=lon,
                accuracy=0.9,
                source="memory",
            ))
        
        return result
    
    def get_wifi_location(self, network_name: str) -> Optional[GeoLocation]:
        """Get location associated with a Wi-Fi network."""
        for frame in reversed(self._frames):
            if frame.raw_data.get("network_name") == network_name and frame.location:
                return frame.location
        return None
    
    def is_known_environment(self, network_name: str) -> bool:
        """Check if a Wi-Fi network is known."""
        return network_name in self._known_wifi
    
    def get_frame_count(self) -> int:
        """Get total number of stored frames."""
        return len(self._frames)
    
    def _haversine_km(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in km."""
        R = 6371.0  # Earth radius in km
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
