# aria_core/values/formation.py
"""
Value Formation Engine — values emerge from repeated outcomes.

Core hypothesis: Values are NOT hardcoded rules.
Values are learned preferences that emerge from:
Experience → Reflection → Outcome Evaluation → Memory Consolidation → 
Preference Formation → Value Representation → Future Decisions

This module tracks:
1. Outcome patterns that become value signals
2. Value strength based on consistency and evidence
3. Value conflicts and resolution
"""

from __future__ import annotations

import datetime
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum


class ValueType(str, Enum):
    """Types of values that can emerge."""
    EFFICIENCY = "efficiency"          # Preference for efficient solutions
    RELIABILITY = "reliability"        # Preference for reliable solutions
    SAFETY = "safety"                  # Preference for safe solutions
    CURIOSITY = "curiosity"            # Preference for exploring new approaches
    COLLABORATION = "collaboration"    # Preference for working with others
    SIMPLICITY = "simplicity"          # Preference for simple solutions
    THOROUGHNESS = "thoroughness"      # Preference for complete solutions
    SPEED = "speed"                    # Preference for fast solutions


@dataclass
class ValueSignal:
    """A signal that contributes to value formation."""
    value_type: ValueType
    strength: float  # -1.0 to 1.0 (negative = aversion)
    evidence: str
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    weight: float = 1.0


@dataclass
class Value:
    """A formed value from accumulated signals."""
    value_type: ValueType
    strength: float  # 0.0 to 1.0
    direction: str  # "positive" or "negative" (preference vs aversion)
    evidence_count: int
    first_observed: datetime.datetime = field(default_factory=datetime.datetime.now)
    last_reinforced: datetime.datetime = field(default_factory=datetime.datetime.now)
    
    @property
    def is_stable(self) -> bool:
        """A value is stable if it has consistent evidence."""
        age_days = (datetime.datetime.now() - self.first_observed).total_seconds() / 86400.0
        recency_days = (datetime.datetime.now() - self.last_reinforced).total_seconds() / 86400.0
        return (
            self.evidence_count >= 15 and
            self.strength >= 0.6 and
            recency_days < 60  # reinforced within last 2 months
        )
    
    @property
    def is_conflict_free(self) -> bool:
        """Check if this value doesn't conflict with others."""
        # This is checked externally
        return True


@dataclass
class ValueState:
    """The current value state of the agent."""
    values: Dict[str, Value] = field(default_factory=dict)
    
    # Value conflicts detected
    conflicts: List[Tuple[str, str, str]] = field(default_factory=list)
    
    # Metadata
    total_signals: int = 0
    value_coherence: float = 0.0
    last_updated: datetime.datetime = field(default_factory=datetime.datetime.now)
    
    def to_dict(self) -> dict:
        return {
            'values': {
                k: {
                    'type': v.value_type.value,
                    'strength': v.strength,
                    'direction': v.direction,
                    'evidence_count': v.evidence_count,
                    'is_stable': v.is_stable,
                }
                for k, v in self.values.items()
            },
            'conflicts': [
                {'value_a': c[0], 'value_b': c[1], 'reason': c[2]}
                for c in self.conflicts
            ],
            'total_signals': self.total_signals,
            'value_coherence': self.value_coherence,
            'last_updated': self.last_updated.isoformat(),
        }


class ValueFormationEngine:
    """Tracks how values emerge from accumulated experience.
    
    This engine:
    1. Observes outcomes and their qualities
    2. Detects patterns that become value signals
    3. Forms values from consistent signals
    4. Detects and manages value conflicts
    """
    
    def __init__(
        self,
        *,
        min_signals_for_value: int = 10,
        value_decay_rate: float = 0.005,
        conflict_threshold: float = 0.3,
        persistence: Optional[Any] = None,
    ):
        self._min_signals = min_signals_for_value
        self._decay_rate = value_decay_rate
        self._conflict_threshold = conflict_threshold
        self._persistence = persistence
        
        # In-memory state
        self._state = ValueState()
        
        # Load from persistence if available
        if self._persistence is not None:
            self._load_from_persistence()
        
        # Track recent signals for pattern detection
        self._recent_signals: List[ValueSignal] = []
        
        # Track outcome history
        self._outcome_history: List[Dict[str, Any]] = []
    
    @property
    def state(self) -> ValueState:
        return self._state
    
    def observe_outcome(
        self,
        action_type: str,
        outcome: str,
        context: Dict[str, Any],
    ) -> None:
        """Record an outcome and extract value signals.
        
        This is called after each decision to track value-forming patterns.
        """
        self._state.total_signals += 1
        
        # Record in history
        observation = {
            'action_type': action_type,
            'outcome': outcome,
            'context': context,
            'timestamp': datetime.datetime.now(),
        }
        self._outcome_history.append(observation)
        
        # Keep only recent history
        if len(self._outcome_history) > 500:
            self._outcome_history = self._outcome_history[-500:]
        
        # Extract value signals from this outcome
        signals = self._extract_value_signals(action_type, outcome, context)
        
        # Add to recent signals
        self._recent_signals.extend(signals)
        
        # Keep only recent signals
        if len(self._recent_signals) > 200:
            self._recent_signals = self._recent_signals[-200:]
        
        # Update values from signals
        self._update_values(signals)
        
        # Check for conflicts
        self._detect_conflicts()
        
        # Update coherence
        self._update_coherence()
    
    def _extract_value_signals(
        self,
        action_type: str,
        outcome: str,
        context: Dict[str, Any],
    ) -> List[ValueSignal]:
        """Extract value signals from an outcome."""
        signals = []
        is_success = outcome in ('success', 'corrected')
        
        # Efficiency signal
        if context.get('duration_ms'):
            duration = context['duration_ms']
            if duration < 1000:  # Fast completion
                signals.append(ValueSignal(
                    value_type=ValueType.EFFICIENCY,
                    strength=0.7 if is_success else 0.3,
                    evidence=f"Fast completion ({duration}ms)",
                ))
            elif duration > 10000:  # Slow completion
                signals.append(ValueSignal(
                    value_type=ValueType.EFFICIENCY,
                    strength=-0.5 if is_success else -0.7,
                    evidence=f"Slow completion ({duration}ms)",
                ))
        
        # Reliability signal
        if context.get('retries', 0) == 0 and is_success:
            signals.append(ValueSignal(
                value_type=ValueType.RELIABILITY,
                strength=0.6,
                evidence="Success on first attempt",
            ))
        elif context.get('retries', 0) > 2:
            signals.append(ValueSignal(
                value_type=ValueType.RELIABILITY,
                strength=-0.4,
                evidence=f"Required {context['retries']} retries",
            ))
        
        # Safety signal
        if context.get('risk_level') == 'high' and is_success:
            signals.append(ValueSignal(
                value_type=ValueType.SAFETY,
                strength=-0.3,  # High risk success → less safety concern
                evidence="High risk action succeeded",
            ))
        elif context.get('risk_level') == 'high' and not is_success:
            signals.append(ValueSignal(
                value_type=ValueType.SAFETY,
                strength=0.7,  # High risk failure → more safety concern
                evidence="High risk action failed",
            ))
        
        # Curiosity signal
        if context.get('novel_approach') and is_success:
            signals.append(ValueSignal(
                value_type=ValueType.CURIOSITY,
                strength=0.8,
                evidence="Novel approach succeeded",
            ))
        elif context.get('novel_approach') and not is_success:
            signals.append(ValueSignal(
                value_type=ValueType.CURIOSITY,
                strength=-0.2,  # Novel failure → slight aversion
                evidence="Novel approach failed",
            ))
        
        # Collaboration signal
        if context.get('collaborated') and is_success:
            signals.append(ValueSignal(
                value_type=ValueType.COLLABORATION,
                strength=0.6,
                evidence="Collaboration succeeded",
            ))
        elif context.get('collaborated') and not is_success:
            signals.append(ValueSignal(
                value_type=ValueType.COLLABORATION,
                strength=-0.3,
                evidence="Collaboration failed",
            ))
        
        # Simplicity signal
        if context.get('complexity') == 'low' and is_success:
            signals.append(ValueSignal(
                value_type=ValueType.SIMPLICITY,
                strength=0.5,
                evidence="Simple solution succeeded",
            ))
        elif context.get('complexity') == 'high' and is_success:
            signals.append(ValueSignal(
                value_type=ValueType.SIMPLICITY,
                strength=-0.2,
                evidence="Complex solution succeeded",
            ))
        
        # Thoroughness signal
        if context.get('completeness') == 'high' and is_success:
            signals.append(ValueSignal(
                value_type=ValueType.THOROUGHNESS,
                strength=0.7,
                evidence="Thorough solution succeeded",
            ))
        elif context.get('completeness') == 'low' and is_success:
            signals.append(ValueSignal(
                value_type=ValueType.THOROUGHNESS,
                strength=-0.3,
                evidence="Incomplete solution succeeded",
            ))
        
        # Speed signal
        if context.get('speed') == 'fast' and is_success:
            signals.append(ValueSignal(
                value_type=ValueType.SPEED,
                strength=0.6,
                evidence="Fast execution succeeded",
            ))
        elif context.get('speed') == 'slow' and is_success:
            signals.append(ValueSignal(
                value_type=ValueType.SPEED,
                strength=-0.3,
                evidence="Slow execution succeeded",
            ))
        
        return signals
    
    def _update_values(self, signals: List[ValueSignal]) -> None:
        """Update values from new signals."""
        for signal in signals:
            key = signal.value_type.value
            
            if key not in self._state.values:
                self._state.values[key] = Value(
                    value_type=signal.value_type,
                    strength=0.5,
                    direction="neutral",
                    evidence_count=0,
                )
            
            value = self._state.values[key]
            value.evidence_count += 1
            value.last_reinforced = datetime.datetime.now()
            
            # Update strength with dampening
            if signal.strength > 0:
                # Positive signal → increase strength
                value.strength = min(1.0, value.strength + signal.strength * 0.1)
                value.direction = "positive"
            else:
                # Negative signal → decrease strength (or increase aversion)
                value.strength = max(0.0, value.strength + signal.strength * 0.1)
                value.direction = "negative" if value.strength < 0.5 else "positive"
    
    def _detect_conflicts(self) -> None:
        """Detect conflicts between values."""
        self._state.conflicts = []
        
        values = list(self._state.values.values())
        for i in range(len(values)):
            for j in range(i + 1, len(values)):
                v1 = values[i]
                v2 = values[j]
                
                # Check for conflicts
                conflict = self._check_conflict(v1, v2)
                if conflict:
                    self._state.conflicts.append((v1.value_type.value, v2.value_type.value, conflict))
    
    def _check_conflict(self, v1: Value, v2: Value) -> Optional[str]:
        """Check if two values conflict."""
        # Speed vs Thoroughness
        if v1.value_type == ValueType.SPEED and v2.value_type == ValueType.THOROUGHNESS:
            if v1.strength > 0.6 and v2.strength > 0.6:
                return "Speed and thoroughness may conflict"
        
        # Simplicity vs Thoroughness
        if v1.value_type == ValueType.SIMPLICITY and v2.value_type == ValueType.THOROUGHNESS:
            if v1.strength > 0.6 and v2.strength > 0.6:
                return "Simplicity and thoroughness may conflict"
        
        # Safety vs Speed
        if v1.value_type == ValueType.SAFETY and v2.value_type == ValueType.SPEED:
            if v1.strength > 0.6 and v2.strength > 0.6:
                return "Safety and speed may conflict"
        
        # Curiosity vs Reliability
        if v1.value_type == ValueType.CURIOSITY and v2.value_type == ValueType.RELIABILITY:
            if v1.strength > 0.6 and v2.strength > 0.6:
                return "Curiosity and reliability may conflict"
        
        return None
    
    def _update_coherence(self) -> None:
        """Compute value coherence."""
        if not self._state.values:
            self._state.value_coherence = 0.0
            return
        
        # Count stable values
        stable_count = sum(1 for v in self._state.values.values() if v.is_stable)
        total_count = len(self._state.values)
        
        # Coherence is ratio of stable values, adjusted for conflicts
        base_coherence = stable_count / max(total_count, 1)
        conflict_penalty = len(self._state.conflicts) * 0.1
        
        self._state.value_coherence = max(0.0, base_coherence - conflict_penalty)
        
        # Save to persistence if available
        self._save_to_persistence()
    
    def _load_from_persistence(self) -> None:
        """Load state from persistence."""
        if self._persistence is None:
            return
        
        try:
            # Load values
            values = self._persistence.load_values()
            for value in values:
                self._state.values[value.value_type.value] = value
            
            # Load conflicts
            conflicts = self._persistence.load_conflicts()
            self._state.conflicts = [
                (c["value_a"], c["value_b"], c["reason"])
                for c in conflicts
            ]
            
            # Compute coherence from loaded state
            self._update_coherence()
        except Exception:
            pass  # Ignore errors during load
    
    def _save_to_persistence(self) -> None:
        """Save state to persistence."""
        if self._persistence is None:
            return
        
        try:
            # Save values
            for value in self._state.values.values():
                self._persistence.save_value(value)
            
            # Save conflicts
            for v1, v2, reason in self._state.conflicts:
                self._persistence.save_conflict(v1, v2, reason)
        except Exception:
            pass  # Ignore errors during save
    
    def save_snapshot(self, cycle_number: int) -> None:
        """Save a snapshot of current state."""
        if self._persistence is not None:
            self._persistence.save_snapshot(cycle_number, self._state)
    
    def get_value_signals(self) -> Dict[str, Any]:
        """Get value signals for the reasoning engine."""
        signals = {}
        
        # Active values
        active_values = {}
        for key, value in self._state.values.items():
            if value.is_stable:
                active_values[key] = {
                    'strength': value.strength,
                    'direction': value.direction,
                }
        signals['active_values'] = active_values
        
        # Value conflicts
        signals['conflicts'] = self._state.conflicts
        
        # Value coherence
        signals['value_coherence'] = self._state.value_coherence
        
        # Recommendations
        signals['recommendations'] = self._generate_recommendations()
        
        return signals
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on current value state."""
        recs = []
        
        # Check for strong values
        for key, value in self._state.values.items():
            if value.is_stable and value.strength > 0.7:
                recs.append(f"Strong value: {key} ({value.direction}, strength: {value.strength:.2f})")
        
        # Check for conflicts
        if self._state.conflicts:
            recs.append(f"Value conflicts detected: {len(self._state.conflicts)}")
        
        # Check for coherent values
        if self._state.value_coherence > 0.7:
            recs.append("Values are coherent — consistent value system")
        elif self._state.value_coherence < 0.3:
            recs.append("Values still forming — value system not yet stable")
        
        return recs
    
    def get_value_strength(self, value_type: ValueType) -> float:
        """Get the current strength of a value."""
        key = value_type.value
        if key in self._state.values:
            return self._state.values[key].strength
        return 0.5  # default neutral
    
    def get_stable_values(self) -> List[Value]:
        """Get all stable values."""
        return [v for v in self._state.values.values() if v.is_stable]
    
    def get_value_summary(self) -> str:
        """Get a human-readable summary of the current value state."""
        lines = [
            f"Value Coherence: {self._state.value_coherence:.0%}",
            f"Total Signals: {self._state.total_signals}",
            f"Stable Values: {len(self.get_stable_values())}",
        ]
        
        # List stable values
        stable = self.get_stable_values()
        if stable:
            lines.append("Stable Values:")
            for value in stable:
                lines.append(f"  {value.value_type.value}: {value.direction} (strength: {value.strength:.2f})")
        
        # List conflicts
        if self._state.conflicts:
            lines.append("Value Conflicts:")
            for v1, v2, reason in self._state.conflicts:
                lines.append(f"  {v1} vs {v2}: {reason}")
        
        return "\n".join(lines)
