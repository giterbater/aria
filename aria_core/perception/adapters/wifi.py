# aria_core/perception/adapters/wifi.py
"""
Wi-Fi Adapter — detects environment context from Wi-Fi networks.

Research question: Can Wi-Fi networks provide environmental context?

Capabilities:
- Detect known networks (home, work, etc.)
- Estimate location from network names
- Determine environmental familiarity
- Provide confidence based on signal strength

Example:
    Known Home Wi-Fi → Memory → "Likely at home" → Reasoning changes
"""

from __future__ import annotations

import datetime
from typing import Optional

from ..models import (
    PerceptionFrame,
    GeoLocation,
    EnvironmentType,
)


class WiFiAdapter:
    """
    Adapter that uses Wi-Fi networks for environmental context.
    
    Usage:
        adapter = WiFiAdapter()
        adapter.add_known_network("HomeNetwork", "home")
        adapter.add_known_network("OfficeWiFi", "office")
        
        frame = adapter.get_current_perception()
        # Frame contains location context from Wi-Fi
    """
    
    def __init__(self):
        self._source_name = "wifi"
        self._known_networks: dict[str, str] = {}  # name -> location_label
        self._current_network: Optional[str] = None
        self._signal_strength: float = 0.0
        self._available: bool = False
    
    def add_known_network(self, network_name: str, location_label: str) -> None:
        """Add a known Wi-Fi network with location label."""
        self._known_networks[network_name] = location_label
    
    def update_scan(self, networks: list[dict]) -> None:
        """
        Update with latest Wi-Fi scan results.
        
        Args:
            networks: List of dicts with 'name' and 'signal' keys
        """
        if not networks:
            self._current_network = None
            self._signal_strength = 0.0
            self._available = False
            return
        
        self._available = True
        
        # Find strongest known network
        best_signal = -100
        best_network = None
        
        for net in networks:
            name = net.get("name", "")
            signal = net.get("signal", -100)
            
            if name in self._known_networks and signal > best_signal:
                best_signal = signal
                best_network = name
        
        self._current_network = best_network
        self._signal_strength = max(0, min(1, (best_signal + 100) / 100))
    
    def get_current_perception(self) -> PerceptionFrame:
        """Get perception frame from Wi-Fi context."""
        if not self._available or self._current_network is None:
            return PerceptionFrame(
                source=self._source_name,
                environment_type=EnvironmentType.UNKNOWN,
                overall_confidence=0.0,
                completeness=0.2,
            )
        
        location_label = self._known_networks.get(self._current_network, "unknown")
        
        # Estimate location from network
        location = GeoLocation(
            latitude=0.0,
            longitude=0.0,
            accuracy=self._signal_strength,
            source="wifi",
        )
        
        # Determine environment type
        env_type = self._infer_environment_type(location_label)
        
        return PerceptionFrame(
            timestamp=datetime.datetime.now(),
            source=self._source_name,
            environment_type=env_type,
            location=location,
            overall_confidence=self._signal_strength,
            completeness=0.4,
            raw_data={
                "network_name": self._current_network,
                "location_label": location_label,
                "signal_strength": self._signal_strength,
            },
        )
    
    def get_location(self) -> Optional[GeoLocation]:
        """Get location from Wi-Fi (limited accuracy)."""
        if self._current_network is None:
            return None
        
        return GeoLocation(
            latitude=0.0,
            longitude=0.0,
            accuracy=self._signal_strength,
            source="wifi",
        )
    
    def is_available(self) -> bool:
        """Check if Wi-Fi scanning is available."""
        return self._available
    
    def get_confidence(self) -> float:
        """Get confidence based on signal strength."""
        return self._signal_strength
    
    def get_source_name(self) -> str:
        """Return source name."""
        return self._source_name
    
    def get_location_label(self) -> Optional[str]:
        """Get the location label for current network."""
        if self._current_network is None:
            return None
        return self._known_networks.get(self._current_network)
    
    def is_known_environment(self) -> bool:
        """Check if current environment is known."""
        return self._current_network is not None
    
    def _infer_environment_type(self, label: str) -> EnvironmentType:
        """Infer environment type from location label."""
        label_lower = label.lower()
        
        if "home" in label_lower or "house" in label_lower:
            return EnvironmentType.INDOOR
        elif "office" in label_lower or "work" in label_lower:
            return EnvironmentType.INDOOR
        elif "cafe" in label_lower or "coffee" in label_lower:
            return EnvironmentType.INDOOR
        elif "park" in label_lower or "outdoor" in label_lower:
            return EnvironmentType.OUTDOOR
        else:
            return EnvironmentType.UNKNOWN
