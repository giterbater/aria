# aria_core/identity/formation.py
"""
Identity Formation Engine — identity emerges from accumulated experience.

Core hypothesis: Identity is NOT a personality preset.
Identity is the compressed result of lived experience.

The formation pipeline:
Experience → Reflection → Memory → Repeated Success/Failure → 
Stable Preferences → Identity Representation → Planning Bias

This module tracks:
1. Behavioral patterns that become stable over time
2. Preference formation from repeated choices
3. Identity representation that influences future decisions
"""

from __future__ import annotations

import datetime
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum


class IdentityDimension(str, Enum):
    """Dimensions along which identity can form."""
    ACTION_PREFERENCE = "action_preference"      # What actions does the agent prefer?
    RISK_TOLERANCE = "risk_tolerance"            # How cautious vs bold?
    SOCIAL_ORIENTED = "social_oriented"          # How much does the agent value social interactions?
    KNOWLEDGE_SEEKING = "knowledge_seeking"      # How much does the agent seek new knowledge?
    PERSISTENCE_STYLE = "persistence_style"      # How does the agent handle failure?
    EXPERTISE_FOCUS = "expertise_focus"          # What areas does the agent specialize in?
    COMMUNICATION_STYLE = "communication_style"  # How does the agent communicate?


@dataclass
class Preference:
    """A formed preference from repeated experience."""
    dimension: IdentityDimension
    value: str  # The preferred value (e.g., "query", "cautious", "bold")
    strength: float  # 0.0 to 1.0, how strong this preference is
    evidence_count: int  # How many experiences support this
    first_observed: datetime.datetime = field(default_factory=datetime.datetime.now)
    last_reinforced: datetime.datetime = field(default_factory=datetime.datetime.now)
    
    @property
    def is_stable(self) -> bool:
        """A preference is stable if it has enough evidence and recent reinforcement."""
        age_days = (datetime.datetime.now() - self.first_observed).total_seconds() / 86400.0
        recency_days = (datetime.datetime.now() - self.last_reinforced).total_seconds() / 86400.0
        return (
            self.evidence_count >= 10 and
            self.strength >= 0.6 and
            recency_days < 30  # reinforced within last month
        )


@dataclass
class IdentityState:
    """The current identity state of the agent."""
    preferences: Dict[str, Preference] = field(default_factory=dict)
    
    # Stable traits that have emerged
    stable_traits: Dict[str, float] = field(default_factory=dict)
    
    # Metadata
    total_experiences: int = 0
    identity_coherence: float = 0.0  # How consistent is the identity?
    last_updated: datetime.datetime = field(default_factory=datetime.datetime.now)
    
    def to_dict(self) -> dict:
        return {
            'preferences': {
                k: {
                    'dimension': v.dimension.value,
                    'value': v.value,
                    'strength': v.strength,
                    'evidence_count': v.evidence_count,
                    'is_stable': v.is_stable,
                }
                for k, v in self.preferences.items()
            },
            'stable_traits': self.stable_traits,
            'total_experiences': self.total_experiences,
            'identity_coherence': self.identity_coherence,
            'last_updated': self.last_updated.isoformat(),
        }
    
    def get_preference(self, dimension: IdentityDimension) -> Optional[Preference]:
        """Get the current preference for a dimension."""
        return self.preferences.get(dimension.value)
    
    def get_trait(self, trait: str) -> float:
        """Get a stable trait value (0.0 to 1.0)."""
        return self.stable_traits.get(trait, 0.5)  # default to neutral


class IdentityFormationEngine:
    """Tracks how identity emerges from accumulated experience.
    
    This engine:
    1. Observes repeated behaviors and outcomes
    2. Detects when behaviors become stable preferences
    3. Computes identity coherence
    4. Provides identity signals for reasoning
    """
    
    def __init__(
        self,
        *,
        min_episodes_for_preference: int = 5,
        preference_decay_rate: float = 0.01,
        coherence_threshold: float = 0.6,
        persistence: Optional[Any] = None,
    ):
        self._min_episodes = min_episodes_for_preference
        self._decay_rate = preference_decay_rate
        self._coherence_threshold = coherence_threshold
        self._persistence = persistence
        
        # In-memory state
        self._state = IdentityState()
        
        # Load from persistence if available
        if self._persistence is not None:
            self._load_from_persistence()
        
        # Track action history for preference formation
        self._action_history: List[Dict[str, Any]] = []
        
        # Track outcome patterns
        self._outcome_patterns: Dict[str, List[bool]] = {}
    
    @property
    def state(self) -> IdentityState:
        return self._state
    
    def observe_action(
        self,
        action_type: str,
        outcome: str,
        context: Dict[str, Any],
    ) -> None:
        """Record an action and its outcome for identity formation.
        
        This is called after each decision to track behavioral patterns.
        """
        self._state.total_experiences += 1
        
        # Record in action history
        observation = {
            'action_type': action_type,
            'outcome': outcome,
            'context': context,
            'timestamp': datetime.datetime.now(),
        }
        self._action_history.append(observation)
        
        # Keep only recent history (last 1000 actions)
        if len(self._action_history) > 1000:
            self._action_history = self._action_history[-1000:]
        
        # Track outcome patterns
        is_success = outcome in ('success', 'corrected')
        if action_type not in self._outcome_patterns:
            self._outcome_patterns[action_type] = []
        self._outcome_patterns[action_type].append(is_success)
        
        # Keep only recent outcomes (last 100 per action type)
        if len(self._outcome_patterns[action_type]) > 100:
            self._outcome_patterns[action_type] = self._outcome_patterns[action_type][-100:]
        
        # Update preferences
        self._update_preferences(action_type, outcome, context)
        
        # Update identity coherence
        self._update_coherence()
    
    def _update_preferences(
        self,
        action_type: str,
        outcome: str,
        context: Dict[str, Any],
    ) -> None:
        """Update preferences based on observed action and outcome."""
        is_success = outcome in ('success', 'corrected')
        
        # Update action preference
        self._update_action_preference(action_type, is_success)
        
        # Update risk tolerance based on outcome
        if context.get('risk_level'):
            self._update_risk_tolerance(context['risk_level'], is_success)
        
        # Update social orientation
        if context.get('social_interaction'):
            self._update_social_orientation(is_success)
        
        # Update knowledge seeking
        if context.get('knowledge_acquired'):
            self._update_knowledge_seeking(is_success)
        
        # Update persistence style
        if context.get('retried'):
            self._update_persistence_style(is_success)
    
    def _update_action_preference(self, action_type: str, is_success: bool) -> None:
        """Update preference for a specific action type."""
        key = f"action_{action_type}"
        
        if key not in self._state.preferences:
            self._state.preferences[key] = Preference(
                dimension=IdentityDimension.ACTION_PREFERENCE,
                value=action_type,
                strength=0.5,
                evidence_count=0,
            )
        
        pref = self._state.preferences[key]
        pref.evidence_count += 1
        pref.last_reinforced = datetime.datetime.now()
        
        # Update strength based on success
        if is_success:
            pref.strength = min(1.0, pref.strength + 0.05)
        else:
            pref.strength = max(0.0, pref.strength - 0.03)
    
    def _update_risk_tolerance(self, risk_level: str, is_success: bool) -> None:
        """Update risk tolerance based on outcomes."""
        key = "risk_tolerance"
        
        if key not in self._state.preferences:
            self._state.preferences[key] = Preference(
                dimension=IdentityDimension.RISK_TOLERANCE,
                value="moderate",
                strength=0.5,
                evidence_count=0,
            )
        
        pref = self._state.preferences[key]
        pref.evidence_count += 1
        pref.last_reinforced = datetime.datetime.now()
        
        # Adjust tolerance based on risk level and outcome
        if risk_level == "high" and is_success:
            # High risk success → more tolerance
            pref.strength = min(1.0, pref.strength + 0.08)
            pref.value = "bold"
        elif risk_level == "low" and is_success:
            # Low risk success → more caution
            pref.strength = min(1.0, pref.strength + 0.05)
            pref.value = "cautious"
        elif risk_level == "high" and not is_success:
            # High risk failure → less tolerance
            pref.strength = max(0.0, pref.strength - 0.1)
            pref.value = "cautious"
    
    def _update_social_orientation(self, is_success: bool) -> None:
        """Update social orientation based on interaction outcomes."""
        key = "social_oriented"
        
        if key not in self._state.preferences:
            self._state.preferences[key] = Preference(
                dimension=IdentityDimension.SOCIAL_ORIENTED,
                value="moderate",
                strength=0.5,
                evidence_count=0,
            )
        
        pref = self._state.preferences[key]
        pref.evidence_count += 1
        pref.last_reinforced = datetime.datetime.now()
        
        if is_success:
            pref.strength = min(1.0, pref.strength + 0.05)
            pref.value = "social"
        else:
            pref.strength = max(0.0, pref.strength - 0.03)
            pref.value = "reserved"
    
    def _update_knowledge_seeking(self, is_success: bool) -> None:
        """Update knowledge seeking preference."""
        key = "knowledge_seeking"
        
        if key not in self._state.preferences:
            self._state.preferences[key] = Preference(
                dimension=IdentityDimension.KNOWLEDGE_SEEKING,
                value="moderate",
                strength=0.5,
                evidence_count=0,
            )
        
        pref = self._state.preferences[key]
        pref.evidence_count += 1
        pref.last_reinforced = datetime.datetime.now()
        
        if is_success:
            pref.strength = min(1.0, pref.strength + 0.06)
            pref.value = "curious"
        else:
            pref.strength = max(0.0, pref.strength - 0.02)
            pref.value = "focused"
    
    def _update_persistence_style(self, is_success: bool) -> None:
        """Update persistence style based on retry outcomes."""
        key = "persistence_style"
        
        if key not in self._state.preferences:
            self._state.preferences[key] = Preference(
                dimension=IdentityDimension.PERSISTENCE_STYLE,
                value="moderate",
                strength=0.5,
                evidence_count=0,
            )
        
        pref = self._state.preferences[key]
        pref.evidence_count += 1
        pref.last_reinforced = datetime.datetime.now()
        
        if is_success:
            pref.strength = min(1.0, pref.strength + 0.07)
            pref.value = "persistent"
        else:
            pref.strength = max(0.0, pref.strength - 0.04)
            pref.value = "adaptive"
    
    def _update_coherence(self) -> None:
        """Compute identity coherence (how consistent are the preferences?)."""
        if not self._state.preferences:
            self._state.identity_coherence = 0.0
            return
        
        # Count stable preferences
        stable_count = sum(1 for p in self._state.preferences.values() if p.is_stable)
        total_count = len(self._state.preferences)
        
        # Coherence is ratio of stable preferences
        self._state.identity_coherence = stable_count / max(total_count, 1)
        
        # Update stable traits from stable preferences
        for key, pref in self._state.preferences.items():
            if pref.is_stable:
                # Convert preference to trait value
                if pref.value in ("bold", "social", "curious", "persistent"):
                    trait_value = pref.strength
                elif pref.value in ("cautious", "reserved", "focused", "adaptive"):
                    trait_value = 1.0 - pref.strength
                else:
                    trait_value = 0.5
                
                self._state.stable_traits[pref.dimension.value] = trait_value
        
        # Save to persistence if available
        self._save_to_persistence()
    
    def _load_from_persistence(self) -> None:
        """Load state from persistence."""
        if self._persistence is None:
            return
        
        try:
            # Load preferences
            preferences = self._persistence.load_preferences()
            for pref in preferences:
                key = f"action_{pref.value}" if pref.dimension == IdentityDimension.ACTION_PREFERENCE else pref.dimension.value
                self._state.preferences[key] = pref
            
            # Load traits
            self._state.stable_traits = self._persistence.load_traits()
            
            # Compute coherence from loaded state
            self._update_coherence()
        except Exception:
            pass  # Ignore errors during load
    
    def _save_to_persistence(self) -> None:
        """Save state to persistence."""
        if self._persistence is None:
            return
        
        try:
            # Save preferences
            for pref in self._state.preferences.values():
                self._persistence.save_preference(pref)
            
            # Save traits
            for trait_name, trait_value in self._state.stable_traits.items():
                self._persistence.save_trait(trait_name, trait_value)
        except Exception:
            pass  # Ignore errors during save
    
    def save_snapshot(self, cycle_number: int) -> None:
        """Save a snapshot of current state."""
        if self._persistence is not None:
            self._persistence.save_snapshot(cycle_number, self._state)
    
    def get_identity_signals(self) -> Dict[str, Any]:
        """Get identity signals for the reasoning engine.
        
        Returns a dict of signals that can bias planning decisions.
        """
        signals = {}
        
        # Action preferences
        action_prefs = {}
        for key, pref in self._state.preferences.items():
            if key.startswith("action_"):
                action_type = key.replace("action_", "")
                if pref.is_stable:
                    action_prefs[action_type] = pref.strength
        signals['action_preferences'] = action_prefs
        
        # Stable traits
        signals['stable_traits'] = self._state.stable_traits.copy()
        
        # Identity coherence
        signals['identity_coherence'] = self._state.identity_coherence
        
        # Recommendations based on identity
        signals['recommendations'] = self._generate_recommendations()
        
        return signals
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on current identity state."""
        recs = []
        
        # Check for strong preferences
        for key, pref in self._state.preferences.items():
            if pref.is_stable and pref.strength > 0.7:
                if key.startswith("action_"):
                    action = key.replace("action_", "")
                    recs.append(f"Strong preference for '{action}' (strength: {pref.strength:.2f})")
        
        # Check for coherent identity
        if self._state.identity_coherence > 0.7:
            recs.append("Identity is coherent — consistent behavior patterns")
        elif self._state.identity_coherence < 0.3:
            recs.append("Identity is forming — behavior patterns still emerging")
        
        return recs
    
    def get_preference_strength(self, dimension: IdentityDimension) -> float:
        """Get the current strength of a preference dimension."""
        key = dimension.value
        if key in self._state.preferences:
            return self._state.preferences[key].strength
        return 0.5  # default neutral
    
    def get_stable_preferences(self) -> List[Preference]:
        """Get all stable preferences."""
        return [p for p in self._state.preferences.values() if p.is_stable]
    
    def get_identity_summary(self) -> str:
        """Get a human-readable summary of the current identity state."""
        lines = [
            f"Identity Coherence: {self._state.identity_coherence:.0%}",
            f"Total Experiences: {self._state.total_experiences}",
            f"Stable Preferences: {len(self.get_stable_preferences())}",
        ]
        
        # List stable traits
        if self._state.stable_traits:
            lines.append("Stable Traits:")
            for trait, value in self._state.stable_traits.items():
                direction = "high" if value > 0.6 else "low" if value < 0.4 else "moderate"
                lines.append(f"  {trait}: {direction} ({value:.2f})")
        
        # List stable preferences
        stable = self.get_stable_preferences()
        if stable:
            lines.append("Stable Preferences:")
            for pref in stable[:5]:
                lines.append(f"  {pref.dimension.value}: {pref.value} (strength: {pref.strength:.2f})")
        
        return "\n".join(lines)
