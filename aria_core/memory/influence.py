# aria_core/memory/influence.py
"""
Memory Influence Engine — makes episodic memory directly shape reasoning.

Core hypothesis: Repeated experiences should create behavioral biases.
If an agent repeatedly succeeds at X, it should prefer X.
If an agent repeatedly fails at Y, it should avoid Y.
If an agent has deep expertise in Z, it should prioritize Z.

This module computes influence signals from memory that the reasoning
engine can consume to bias its decisions.
"""

from __future__ import annotations

import datetime
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .models import MemoryItem, EpisodicItem, SemanticItem, Outcome
from .interfaces import MemorySystemProtocol


@dataclass
class InfluenceSignal:
    """A computed influence from memory on future decisions."""
    
    # What action type this signal favors or disfavors
    action_preference: str  # e.g., "inform", "execute", "query"
    
    # Strength: positive = favor, negative = avoid
    strength: float  # -1.0 to 1.0
    
    # Why this signal exists (for debugging/introspection)
    reason: str
    
    # How many episodes support this signal
    evidence_count: int
    
    # Confidence in this signal (based on evidence quality)
    confidence: float  # 0.0 to 1.0
    
    # Decay factor: older evidence matters less
    recency_weight: float = 1.0


@dataclass
class BehavioralPattern:
    """A detected pattern in the agent's behavior."""
    
    # The pattern description
    pattern: str
    
    # Associated action type
    action_type: str
    
    # Success rate for this pattern
    success_rate: float
    
    # Number of observations
    observation_count: int
    
    # Average importance of episodes with this pattern
    avg_importance: float
    
    # When this pattern was last observed
    last_observed: datetime.datetime = field(default_factory=datetime.datetime.now)


class MemoryInfluenceEngine:
    """Computes influence signals from memory for the reasoning engine.
    
    This engine analyzes:
    1. Success/failure patterns per action type
    2. Repeated behavioral patterns
    3. Expertise areas (high success in specific domains)
    4. Avoidance patterns (repeated failures)
    
    The output is a set of InfluenceSignals that the reasoning engine
    can use to bias its decisions.
    """
    
    def __init__(
        self,
        memory: MemorySystemProtocol,
        *,
        min_episodes_for_pattern: int = 3,
        recency_half_life_days: float = 7.0,
        expertise_threshold: float = 0.7,
        avoidance_threshold: float = 0.3,
    ):
        self._memory = memory
        self._min_episodes = min_episodes_for_pattern
        self._recency_lambda = math.log(2) / recency_half_life_days
        self._expertise_threshold = expertise_threshold
        self._avoidance_threshold = avoidance_threshold
    
    def compute_influences(
        self,
        *,
        limit: int = 20,
        include_patterns: bool = True,
        include_expertise: bool = True,
        include_avoidance: bool = True,
    ) -> List[InfluenceSignal]:
        """Compute all influence signals from memory.
        
        Returns a list of signals sorted by absolute strength (strongest first).
        """
        signals: List[InfluenceSignal] = []
        
        # Get recent episodic memory
        episodes = self._memory.get_episodic(limit=200)
        
        if include_patterns:
            signals.extend(self._compute_action_preferences(episodes))
        
        if include_expertise:
            signals.extend(self._compute_expertise_signals(episodes))
        
        if include_avoidance:
            signals.extend(self._compute_avoidance_signals(episodes))
        
        # Sort by absolute strength
        signals.sort(key=lambda s: abs(s.strength), reverse=True)
        
        return signals[:limit]
    
    def detect_patterns(
        self,
        *,
        min_observations: int | None = None,
    ) -> List[BehavioralPattern]:
        """Detect recurring behavioral patterns in memory.
        
        Returns patterns sorted by observation count (most frequent first).
        """
        min_obs = min_observations or self._min_episodes
        episodes = self._memory.get_episodic(limit=500)
        
        # Group episodes by action type
        action_groups: Dict[str, List[EpisodicItem]] = {}
        for ep in episodes:
            if ep.decision and hasattr(ep.decision, 'action_type'):
                action_type = ep.decision.action_type
                if action_type not in action_groups:
                    action_groups[action_type] = []
                action_groups[action_type].append(ep)
        
        patterns: List[BehavioralPattern] = []
        
        for action_type, group in action_groups.items():
            if len(group) < min_obs:
                continue
            
            # Compute success rate
            successes = sum(
                1 for ep in group
                if ep.outcome in (Outcome.SUCCESS.value, Outcome.CORRECTED.value)
            )
            success_rate = successes / len(group)
            
            # Compute average importance
            avg_importance = sum(ep.importance for ep in group) / len(group)
            
            # Find most recent observation
            last_observed = max(ep.timestamp for ep in group)
            
            # Generate pattern description
            if success_rate > 0.7:
                desc = f"Consistently succeeds at {action_type}"
            elif success_rate < 0.3:
                desc = f"Consistently fails at {action_type}"
            else:
                desc = f"Mixed results with {action_type}"
            
            patterns.append(BehavioralPattern(
                pattern=desc,
                action_type=action_type,
                success_rate=success_rate,
                observation_count=len(group),
                avg_importance=avg_importance,
                last_observed=last_observed,
            ))
        
        patterns.sort(key=lambda p: p.observation_count, reverse=True)
        return patterns
    
    def get_expertise_areas(
        self,
        *,
        min_success_rate: float | None = None,
    ) -> List[Tuple[str, float, int]]:
        """Identify areas where the agent has high expertise.
        
        Returns list of (action_type, success_rate, evidence_count) tuples.
        """
        threshold = min_success_rate or self._expertise_threshold
        episodes = self._memory.get_episodic(limit=500)
        
        action_results: Dict[str, List[bool]] = {}
        for ep in episodes:
            if ep.decision and hasattr(ep.decision, 'action_type'):
                action_type = ep.decision.action_type
                if action_type not in action_results:
                    action_results[action_type] = []
                success = ep.outcome in (Outcome.SUCCESS.value, Outcome.CORRECTED.value)
                action_results[action_type].append(success)
        
        expertise: List[Tuple[str, float, int]] = []
        for action_type, results in action_results.items():
            if len(results) < self._min_episodes:
                continue
            success_rate = sum(results) / len(results)
            if success_rate >= threshold:
                expertise.append((action_type, success_rate, len(results)))
        
        expertise.sort(key=lambda x: (x[1], x[2]), reverse=True)
        return expertise
    
    def get_avoidance_areas(
        self,
        *,
        max_success_rate: float | None = None,
    ) -> List[Tuple[str, float, int]]:
        """Identify areas where the agent should avoid certain actions.
        
        Returns list of (action_type, failure_rate, evidence_count) tuples.
        """
        threshold = max_success_rate or self._avoidance_threshold
        episodes = self._memory.get_episodic(limit=500)
        
        action_results: Dict[str, List[bool]] = {}
        for ep in episodes:
            if ep.decision and hasattr(ep.decision, 'action_type'):
                action_type = ep.decision.action_type
                if action_type not in action_results:
                    action_results[action_type] = []
                success = ep.outcome in (Outcome.SUCCESS.value, Outcome.CORRECTED.value)
                action_results[action_type].append(success)
        
        avoidance: List[Tuple[str, float, int]] = []
        for action_type, results in action_results.items():
            if len(results) < self._min_episodes:
                continue
            success_rate = sum(results) / len(results)
            if success_rate <= threshold:
                failure_rate = 1.0 - success_rate
                avoidance.append((action_type, failure_rate, len(results)))
        
        avoidance.sort(key=lambda x: (x[1], x[2]), reverse=True)
        return avoidance
    
    def _compute_action_preferences(
        self,
        episodes: List[EpisodicItem],
    ) -> List[InfluenceSignal]:
        """Compute preferences for each action type based on success patterns."""
        action_stats: Dict[str, Dict[str, Any]] = {}
        
        for ep in episodes:
            if not ep.decision or not hasattr(ep.decision, 'action_type'):
                continue
            
            action_type = ep.decision.action_type
            if action_type not in action_stats:
                action_stats[action_type] = {
                    'successes': 0,
                    'failures': 0,
                    'total_weight': 0.0,
                    'success_weight': 0.0,
                }
            
            stats = action_stats[action_type]
            
            # Compute recency weight
            age_days = (datetime.datetime.now() - ep.timestamp).total_seconds() / 86400.0
            recency_weight = math.exp(-self._recency_lambda * age_days)
            
            is_success = ep.outcome in (Outcome.SUCCESS.value, Outcome.CORRECTED.value)
            
            if is_success:
                stats['successes'] += 1
                stats['success_weight'] += recency_weight * ep.importance
            else:
                stats['failures'] += 1
            
            stats['total_weight'] += recency_weight
        
        signals: List[InfluenceSignal] = []
        
        for action_type, stats in action_stats.items():
            total = stats['successes'] + stats['failures']
            if total < self._min_episodes:
                continue
            
            success_rate = stats['successes'] / total
            
            # Compute strength based on success rate and evidence
            # Normalize to [-1, 1] where 0.5 is neutral
            strength = (success_rate - 0.5) * 2.0
            
            # Weight by evidence count (more evidence = stronger signal)
            evidence_weight = min(1.0, total / 20.0)
            strength *= evidence_weight
            
            # Compute confidence
            confidence = min(1.0, total / 30.0) * (stats['total_weight'] / max(total, 1))
            
            reason = f"{stats['successes']}/{total} successes ({success_rate:.0%})"
            
            signals.append(InfluenceSignal(
                action_preference=action_type,
                strength=strength,
                reason=reason,
                evidence_count=total,
                confidence=confidence,
                recency_weight=stats['total_weight'] / max(total, 1),
            ))
        
        return signals
    
    def _compute_expertise_signals(
        self,
        episodes: List[EpisodicItem],
    ) -> List[InfluenceSignal]:
        """Compute signals for areas of expertise."""
        expertise = self.get_expertise_areas()
        signals: List[InfluenceSignal] = []
        
        for action_type, success_rate, count in expertise:
            # Expertise creates a positive bias
            strength = (success_rate - 0.5) * 1.5  # Amplify expertise signal
            strength = min(1.0, strength)
            
            confidence = min(1.0, count / 20.0)
            
            signals.append(InfluenceSignal(
                action_preference=action_type,
                strength=strength,
                reason=f"Expertise: {success_rate:.0%} success over {count} episodes",
                evidence_count=count,
                confidence=confidence,
            ))
        
        return signals
    
    def _compute_avoidance_signals(
        self,
        episodes: List[EpisodicItem],
    ) -> List[InfluenceSignal]:
        """Compute signals for areas to avoid."""
        avoidance = self.get_avoidance_areas()
        signals: List[InfluenceSignal] = []
        
        for action_type, failure_rate, count in avoidance:
            # Avoidance creates a negative bias
            strength = -(failure_rate * 1.5)  # Negative for avoidance
            strength = max(-1.0, strength)
            
            confidence = min(1.0, count / 20.0)
            
            signals.append(InfluenceSignal(
                action_preference=action_type,
                strength=strength,
                reason=f"Avoid: {failure_rate:.0%} failure rate over {count} episodes",
                evidence_count=count,
                confidence=confidence,
            ))
        
        return signals
    
    def get_influence_summary(self) -> Dict[str, Any]:
        """Get a summary of all influences for debugging/introspection."""
        signals = self.compute_influences(limit=50)
        patterns = self.detect_patterns()
        expertise = self.get_expertise_areas()
        avoidance = self.get_avoidance_areas()
        
        return {
            'signal_count': len(signals),
            'top_preferences': [
                {
                    'action': s.action_preference,
                    'strength': s.strength,
                    'reason': s.reason,
                }
                for s in signals[:5]
            ],
            'pattern_count': len(patterns),
            'top_patterns': [
                {
                    'pattern': p.pattern,
                    'action': p.action_type,
                    'success_rate': p.success_rate,
                    'observations': p.observation_count,
                }
                for p in patterns[:5]
            ],
            'expertise_areas': [
                {'action': a, 'rate': r, 'count': c}
                for a, r, c in expertise[:5]
            ],
            'avoidance_areas': [
                {'action': a, 'failure_rate': r, 'count': c}
                for a, r, c in avoidance[:5]
            ],
        }
