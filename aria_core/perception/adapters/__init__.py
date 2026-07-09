# aria_core/perception/adapters/__init__.py
"""
Environment Adapters — convert raw data into PerceptionFrame.

Each adapter wraps a specific data source and produces
standardized PerceptionFrame objects.
"""

from .simulation import SimulationAdapter
from .wifi import WiFiAdapter
from .gps import GPSAdapter
from .mock import MockAdapter

__all__ = [
    "SimulationAdapter",
    "WiFiAdapter",
    "GPSAdapter",
    "MockAdapter",
]
