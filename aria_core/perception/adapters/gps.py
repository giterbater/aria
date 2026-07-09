# aria_core/perception/adapters/gps.py
"""
GPS Adapter — provides location from GPS sensor.

Provides geographic coordinates with accuracy information.
Used for navigation, spatial memory, and location-based reasoning.
"""

from __future__ import annotations

import datetime
from typing import Optional

from ..models import (
    PerceptionFrame,
    GeoLocation,
    EnvironmentType,
)


class GPSAdapter:
    """
    Adapter that provides GPS location data.
    
    Usage:
        adapter = GPSAdapter()
        adapter.update_location(latitude=37.7749, longitude=-122.4194, accuracy=10.0)
        
        frame = adapter.get_current_perception()
        # Frame contains GPS location
    """
    
    def __init__(self):
        self._source_name = "gps"
        self._location: Optional[GeoLocation] = None
        self._available: bool = False
        self._last_update: Optional[datetime.datetime] = None
    
    def update_location(
        self,
        latitude: float,
        longitude: float,
        altitude: float = 0.0,
        accuracy: float = 10.0,
    ) -> None:
        """Update current GPS location."""
        # Convert accuracy meters to 0-1 scale (10m = 1.0, 100m = 0.1)
        accuracy_score = max(0.0, min(1.0, 1.0 - (accuracy / 100.0)))
        
        self._location = GeoLocation(
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
            accuracy=accuracy_score,
            source="gps",
        )
        self._available = True
        self._last_update = datetime.datetime.now()
    
    def get_current_perception(self) -> PerceptionFrame:
        """Get perception frame from GPS."""
        if self._location is None:
            return PerceptionFrame(
                source=self._source_name,
                environment_type=EnvironmentType.UNKNOWN,
                overall_confidence=0.0,
                completeness=0.1,
            )
        
        # GPS provides location but not much else
        # Environment type is unknown from GPS alone
        return PerceptionFrame(
            timestamp=datetime.datetime.now(),
            source=self._source_name,
            environment_type=EnvironmentType.UNKNOWN,
            location=self._location,
            overall_confidence=self._location.accuracy,
            completeness=0.3,
            raw_data={
                "latitude": self._location.latitude,
                "longitude": self._location.longitude,
                "altitude": self._location.altitude,
                "accuracy_meters": (1.0 - self._location.accuracy) * 100,
            },
        )
    
    def get_location(self) -> Optional[GeoLocation]:
        """Get current GPS location."""
        return self._location
    
    def is_available(self) -> bool:
        """Check if GPS is available."""
        return self._available
    
    def get_confidence(self) -> float:
        """Get confidence based on accuracy."""
        if self._location is None:
            return 0.0
        return self._location.accuracy
    
    def get_source_name(self) -> str:
        """Return source name."""
        return self._source_name
    
    def get_age_seconds(self) -> float:
        """Get age of last GPS reading in seconds."""
        if self._last_update is None:
            return float("inf")
        return (datetime.datetime.now() - self._last_update).total_seconds()
