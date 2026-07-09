# aria_core/perception/geospatial.py
"""
Geospatial Reasoning — navigation, spatial memory, place recognition.

Provides:
- Navigation (route planning)
- Spatial memory (visited places)
- Place recognition (landmarks)
- Distance estimation
- Resource planning based on location
- Route optimization

Provider-independent — not tightly coupled to any mapping service.
"""

from __future__ import annotations

import math
from typing import Optional, Protocol, runtime_checkable

from .models import GeoLocation, PerceptionFrame


@runtime_checkable
class NavigationProvider(Protocol):
    """Protocol for navigation data providers."""
    
    def get_route(self, start: GeoLocation, end: GeoLocation) -> dict: ...
    def get_distance(self, start: GeoLocation, end: GeoLocation) -> float: ...
    def get_nearby_resources(self, location: GeoLocation, radius_km: float) -> list[dict]: ...


class GeospatialReasoner:
    """
    Geospatial reasoning for location-aware decisions.
    
    Usage:
        reasoner = GeospatialReasoner()
        
        # Store visited locations
        reasoner.record_visit(location)
        
        # Calculate distance
        distance = reasoner.distance_between(loc1, loc2)
        
        # Check if location is familiar
        familiarity = reasoner.get_familiarity(location)
        
        # Get navigation suggestion
        route = reasoner.suggest_route(start, end)
    """
    
    def __init__(self, provider: Optional[NavigationProvider] = None):
        self._provider = provider
        self._visited_locations: list[GeoLocation] = []
        self._location_counts: dict[str, int] = {}
        self._landmarks: list[dict] = []
    
    def record_visit(self, location: GeoLocation) -> None:
        """Record a visit to a location."""
        self._visited_locations.append(location)
        
        loc_key = self._location_key(location)
        self._location_counts[loc_key] = self._location_counts.get(loc_key, 0) + 1
    
    def distance_between(self, loc1: GeoLocation, loc2: GeoLocation) -> float:
        """Calculate distance between two locations in km."""
        return self._haversine_km(
            loc1.latitude, loc1.longitude,
            loc2.latitude, loc2.longitude,
        )
    
    def get_familiarity(self, location: GeoLocation) -> float:
        """
        Get familiarity with a location (0-1).
        
        Higher values mean the location is more familiar.
        """
        loc_key = self._location_key(location)
        visit_count = self._location_counts.get(loc_key, 0)
        
        # Logarithmic scaling: 1 visit = 0.3, 10 visits = 0.7, 100 visits = 0.9
        if visit_count == 0:
            return 0.0
        elif visit_count == 1:
            return 0.3
        else:
            return min(0.95, 0.3 + 0.2 * math.log10(visit_count))
    
    def get_nearest_visited(self, location: GeoLocation) -> Optional[GeoLocation]:
        """Get the nearest visited location."""
        if not self._visited_locations:
            return None
        
        nearest = None
        min_distance = float("inf")
        
        for visited in self._visited_locations:
            dist = self.distance_between(location, visited)
            if dist < min_distance:
                min_distance = dist
                nearest = visited
        
        return nearest
    
    def get_frequently_visited(self, limit: int = 5) -> list[GeoLocation]:
        """Get most frequently visited locations."""
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
    
    def suggest_route(
        self,
        start: GeoLocation,
        end: GeoLocation,
    ) -> Optional[dict]:
        """
        Suggest a route between two locations.
        
        Returns route information if provider available.
        """
        if self._provider:
            try:
                return self._provider.get_route(start, end)
            except Exception:
                pass
        
        # Fallback: simple straight-line estimate
        distance = self.distance_between(start, end)
        return {
            "distance_km": distance,
            "estimated_time_minutes": distance * 3,  # Rough estimate: 20 km/h average
            "route_type": "straight_line",
            "confidence": 0.3,
        }
    
    def estimate_travel_time(
        self,
        start: GeoLocation,
        end: GeoLocation,
        speed_kmh: float = 5.0,
    ) -> float:
        """Estimate travel time in minutes."""
        distance = self.distance_between(start, end)
        return (distance / speed_kmh) * 60
    
    def is_within_radius(
        self,
        location: GeoLocation,
        center: GeoLocation,
        radius_km: float,
    ) -> bool:
        """Check if location is within radius of center."""
        distance = self.distance_between(location, center)
        return distance <= radius_km
    
    def get_location_summary(self, location: GeoLocation) -> dict:
        """Get a summary of a location."""
        familiarity = self.get_familiarity(location)
        nearest = self.get_nearest_visited(location)
        
        return {
            "familiarity": familiarity,
            "visit_count": self._location_counts.get(self._location_key(location), 0),
            "nearest_visited_distance": (
                self.distance_between(location, nearest) if nearest else None
            ),
            "is_familiar": familiarity > 0.5,
        }
    
    def _location_key(self, location: GeoLocation) -> str:
        """Create a key for location (rounded to ~100m precision)."""
        return f"{location.latitude:.4f},{location.longitude:.4f}"
    
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
