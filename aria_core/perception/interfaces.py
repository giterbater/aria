# aria_core/perception/interfaces.py
"""
World Interface API — the protocol every environment must implement.

Design principle: ARIA Core should never know whether data came from:
- Simulation
- Google Earth
- Wi-Fi
- Camera
- Robot sensors
- Internet

Every environment adapter implements this interface and produces
PerceptionFrame objects. ARIA Core consumes only PerceptionFrame.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable, Optional

from .models import PerceptionFrame, PerceptionContext, GeoLocation


@runtime_checkable
class WorldInterface(Protocol):
    """
    Protocol for environment adapters.
    
    Every environment (simulation, GPS, Wi-Fi, camera, etc.)
    must implement this interface.
    
    ARIA Core depends only on this protocol, never on concrete
    implementations. This guarantees complete independence from
    specific sensors or data sources.
    """
    
    def get_current_perception(self) -> PerceptionFrame:
        """
        Get the current perception frame from this environment.
        
        Returns a PerceptionFrame containing:
        - Location
        - Objects
        - Agents
        - Resources
        - Weather
        - Terrain
        - Events
        - Confidence
        
        This is the primary interface. Every adapter implements this.
        """
        ...
    
    def get_location(self) -> Optional[GeoLocation]:
        """
        Get current location from this environment.
        
        May return None if location is unavailable.
        """
        ...
    
    def is_available(self) -> bool:
        """
        Check if this environment is available.
        
        Returns True if the adapter can provide data.
        May return False if sensor is disconnected, etc.
        """
        ...
    
    def get_confidence(self) -> float:
        """
        Get confidence in current perception.
        
        Returns 0.0-1.0 indicating how confident the adapter
        is in its current perception.
        """
        ...
    
    def get_source_name(self) -> str:
        """
        Get the name of this data source.
        
        Used for debugging and logging.
        Examples: "simulation", "gps", "wifi", "camera"
        """
        ...


@runtime_checkable
class SensorFusion(Protocol):
    """
    Protocol for combining multiple perception sources.
    
    Takes multiple WorldInterface instances and produces
    a single fused PerceptionFrame.
    """
    
    def add_source(self, source: WorldInterface) -> None:
        """Add a perception source."""
        ...
    
    def remove_source(self, source: WorldInterface) -> None:
        """Remove a perception source."""
        ...
    
    def fuse(self) -> PerceptionFrame:
        """
        Fuse all sources into a single PerceptionFrame.
        
        Combines data from multiple sensors, resolves conflicts,
        and produces a unified perception.
        """
        ...
    
    def get_confidence(self) -> float:
        """Get confidence in fused perception."""
        ...


@runtime_checkable
class PerceptionMemory(Protocol):
    """
    Protocol for storing and retrieving perception history.
    
    Stores observations for episodic retrieval.
    """
    
    def store(self, frame: PerceptionFrame) -> None:
        """Store a perception frame."""
        ...
    
    def get_recent(self, limit: int = 10) -> list[PerceptionFrame]:
        """Get recent perception frames."""
        ...
    
    def get_by_location(
        self,
        location: GeoLocation,
        radius_km: float = 1.0,
    ) -> list[PerceptionFrame]:
        """Get perception frames near a location."""
        ...
    
    def get_known_wifi_networks(self) -> list[str]:
        """Get list of known Wi-Fi network names."""
        ...
    
    def get_visited_locations(self) -> list[GeoLocation]:
        """Get list of visited locations."""
        ...
    
    def get_frequently_visited(self, limit: int = 10) -> list[GeoLocation]:
        """Get most frequently visited locations."""
        ...


@runtime_checkable
class ContextBuilder(Protocol):
    """
    Protocol for building reasoning context from perception.
    
    Converts raw perception into context suitable for reasoning.
    """
    
    def build_context(self, frame: PerceptionFrame) -> PerceptionContext:
        """
        Build a PerceptionContext from a PerceptionFrame.
        
        Enriches raw perception with:
        - Location history
        - Wi-Fi network recognition
        - Environment familiarity
        - Confidence calculations
        """
        ...
    
    def update_from_memory(
        self,
        context: PerceptionContext,
        memory: PerceptionMemory,
    ) -> PerceptionContext:
        """
        Update context with information from memory.
        
        Adds:
        - Known environment detection
        - Frequently visited places
        - Historical confidence
        """
        ...
