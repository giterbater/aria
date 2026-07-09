# aria_core/perception/adapters/internet.py
"""
Internet Adapter — web-based context perception.

Provides:
- Location from IP address
- Weather from weather services
- News/events from news APIs
- Point of interest data
- Traffic conditions
- Environmental updates

Uses provider-independent interface.
"""

from __future__ import annotations

import datetime
from typing import Optional, Protocol, runtime_checkable

from ..models import (
    PerceptionFrame,
    GeoLocation,
    EnvironmentType,
    WeatherCondition,
    PerceivedWeather,
    PerceivedEvent,
)


@runtime_checkable
class WebDataProvider(Protocol):
    """Protocol for web data providers."""
    
    def get_location_from_ip(self, ip: str) -> dict: ...
    def get_weather(self, lat: float, lon: float) -> dict: ...
    def get_nearby_places(self, lat: float, lon: float) -> list[dict]: ...
    def get_local_news(self, lat: float, lon: float) -> list[dict]: ...


class InternetAdapter:
    """
    Adapter for web-based context perception.
    
    Usage:
        adapter = InternetAdapter()
        adapter.update_from_ip("8.8.8.8")
        
        frame = adapter.get_current_perception()
        # Frame contains location, weather, events from web
    """
    
    def __init__(self, provider: Optional[WebDataProvider] = None):
        self._source_name = "internet"
        self._provider = provider
        self._location: Optional[GeoLocation] = None
        self._weather: Optional[PerceivedWeather] = None
        self._events: list[PerceivedEvent] = []
        self._places: list[dict] = []
        self._available: bool = True
        self._last_update: Optional[datetime.datetime] = None
    
    def update_from_ip(self, ip: str) -> None:
        """Update location from IP address."""
        if self._provider:
            try:
                loc_data = self._provider.get_location_from_ip(ip)
                self._location = GeoLocation(
                    latitude=loc_data.get("lat", 0),
                    longitude=loc_data.get("lon", 0),
                    accuracy=0.5,  # IP geolocation is less accurate
                    source="internet_ip",
                )
                self._last_update = datetime.datetime.now()
            except Exception:
                pass
    
    def update_weather(self, lat: float, lon: float) -> None:
        """Update weather from weather service."""
        if self._provider:
            try:
                weather_data = self._provider.get_weather(lat, lon)
                self._weather = PerceivedWeather(
                    condition=self._parse_condition(weather_data.get("condition", "")),
                    temperature=weather_data.get("temperature", 20.0),
                    wind_speed=weather_data.get("wind_speed", 0.0),
                    visibility=weather_data.get("visibility", 1.0),
                    confidence=0.8,
                )
                self._last_update = datetime.datetime.now()
            except Exception:
                pass
    
    def update_events(self, lat: float, lon: float) -> None:
        """Update local events from news APIs."""
        if self._provider:
            try:
                news_data = self._provider.get_local_news(lat, lon)
                self._events = [
                    PerceivedEvent(
                        event_type="news",
                        description=item.get("title", ""),
                        severity=item.get("severity", 0.5),
                        confidence=0.6,
                    )
                    for item in news_data[:10]
                ]
                self._last_update = datetime.datetime.now()
            except Exception:
                pass
    
    def update_places(self, lat: float, lon: float) -> None:
        """Update nearby points of interest."""
        if self._provider:
            try:
                self._places = self._provider.get_nearby_places(lat, lon)
                self._last_update = datetime.datetime.now()
            except Exception:
                pass
    
    def get_current_perception(self) -> PerceptionFrame:
        """Get perception frame from internet data."""
        if self._location is None:
            return PerceptionFrame(
                source=self._source_name,
                environment_type=EnvironmentType.UNKNOWN,
                overall_confidence=0.0,
                completeness=0.1,
            )
        
        return PerceptionFrame(
            timestamp=datetime.datetime.now(),
            source=self._source_name,
            environment_type=EnvironmentType.UNKNOWN,  # Internet doesn't know environment type
            location=self._location,
            weather=self._weather,
            events=self._events,
            overall_confidence=self._calculate_confidence(),
            completeness=0.5,
            raw_data={
                "places_count": len(self._places),
                "events_count": len(self._events),
                "has_weather": self._weather is not None,
            },
        )
    
    def get_location(self) -> Optional[GeoLocation]:
        """Get location from IP."""
        return self._location
    
    def is_available(self) -> bool:
        """Check if internet is available."""
        return self._available
    
    def get_confidence(self) -> float:
        """Get confidence in internet data."""
        return self._calculate_confidence()
    
    def get_source_name(self) -> str:
        """Return source name."""
        return self._source_name
    
    def get_weather(self) -> Optional[PerceivedWeather]:
        """Get current weather."""
        return self._weather
    
    def get_events(self) -> list[PerceivedEvent]:
        """Get local events."""
        return self._events
    
    def get_places(self) -> list[dict]:
        """Get nearby places."""
        return self._places
    
    def _calculate_confidence(self) -> float:
        """Calculate overall confidence."""
        score = 0.0
        
        if self._location:
            score += 0.3
        if self._weather:
            score += 0.3
        if self._events:
            score += 0.2
        if self._places:
            score += 0.2
        
        return min(1.0, score)
    
    def _parse_condition(self, condition: str) -> WeatherCondition:
        """Parse weather condition string."""
        condition_lower = condition.lower()
        
        if "clear" in condition_lower or "sunny" in condition_lower:
            return WeatherCondition.CLEAR
        elif "cloud" in condition_lower:
            return WeatherCondition.CLOUDY
        elif "rain" in condition_lower:
            return WeatherCondition.RAIN
        elif "snow" in condition_lower:
            return WeatherCondition.SNOW
        elif "storm" in condition_lower or "thunder" in condition_lower:
            return WeatherCondition.STORM
        elif "fog" in condition_lower or "mist" in condition_lower:
            return WeatherCondition.FOG
        else:
            return WeatherCondition.UNKNOWN
