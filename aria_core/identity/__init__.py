# aria_core/identity/__init__.py
"""
Identity Formation Module — identity emerges from accumulated experience.
"""

from .formation import (
    IdentityFormationEngine,
    IdentityState,
    IdentityDimension,
    Preference,
)
from .persistence import IdentityStore

__all__ = [
    'IdentityFormationEngine',
    'IdentityState',
    'IdentityDimension',
    'Preference',
    'IdentityStore',
]
