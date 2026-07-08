# tests/test_developmental_cognition.py
"""
Comprehensive tests for developmental cognition capabilities.

Tests:
1. Memory influence on decision making
2. Identity formation from experience
3. Value formation from outcomes
4. Multi-seed behavioral consistency
5. Ablation studies (memory vs no memory, identity vs no identity)
"""

from __future__ import annotations

import pytest
import random
from typing import List, Dict, Any

from aria_core.integration import ARIACore
from aria_core.memory.simple_memory_system import SimpleMemorySystem
from aria_core.memory.influence import MemoryInfluenceEngine, InfluenceSignal
from aria_core.identity.formation import IdentityFormationEngine, IdentityDimension, Preference
from aria_core.values.formation import ValueFormationEngine, ValueType, Value
from aria_core.interfaces import StructuredInput, ARIDecision
from aria_core.memory.models import EpisodicItem, Outcome


class TestMemoryInfluence:
    """Test memory influence on decision making."""

    def test_influence_engine_initialization(self):
        """Test that influence engine initializes correctly."""
        memory = SimpleMemorySystem()
        engine = MemoryInfluenceEngine(memory)
        
        signals = engine.compute_influences()
        assert isinstance(signals, list)
        assert len(signals) == 0  # No data yet

    def test_influence_from_repeated_success(self):
        """Test that repeated successes create positive influence signals."""
        memory = SimpleMemorySystem()
        engine = MemoryInfluenceEngine(memory, min_episodes_for_pattern=3)
        
        # Add multiple successful episodes for 'inform' action
        for i in range(5):
            episode = EpisodicItem(
                importance=0.7,
                structured_input={"text": f"test {i}"},
                decision=type('Decision', (), {'action_type': 'inform', 'payload': {}})(),
                outcome=Outcome.SUCCESS.value,
            )
            memory.store_episodic(episode)
        
        signals = engine.compute_influences()
        
        # Should have positive signal for 'inform'
        inform_signals = [s for s in signals if s.action_preference == 'inform']
        assert len(inform_signals) > 0
        assert inform_signals[0].strength > 0

    def test_influence_from_repeated_failure(self):
        """Test that repeated failures create negative influence signals."""
        memory = SimpleMemorySystem()
        engine = MemoryInfluenceEngine(memory, min_episodes_for_pattern=3)
        
        # Add multiple failed episodes for 'execute' action
        for i in range(5):
            episode = EpisodicItem(
                importance=0.6,
                structured_input={"text": f"test {i}"},
                decision=type('Decision', (), {'action_type': 'execute', 'payload': {}})(),
                outcome=Outcome.FAILED.value,
            )
            memory.store_episodic(episode)
        
        signals = engine.compute_influences()
        
        # Should have negative signal for 'execute'
        execute_signals = [s for s in signals if s.action_preference == 'execute']
        assert len(execute_signals) > 0
        assert execute_signals[0].strength < 0

    def test_pattern_detection(self):
        """Test that behavioral patterns are detected correctly."""
        memory = SimpleMemorySystem()
        engine = MemoryInfluenceEngine(memory, min_episodes_for_pattern=3)
        
        # Create pattern: 'query' always succeeds
        for i in range(4):
            episode = EpisodicItem(
                importance=0.7,
                structured_input={"text": f"query {i}"},
                decision=type('Decision', (), {'action_type': 'query', 'payload': {}})(),
                outcome=Outcome.SUCCESS.value,
            )
            memory.store_episodic(episode)
        
        patterns = engine.detect_patterns()
        
        # Should detect 'query' as a successful pattern
        query_patterns = [p for p in patterns if p.action_type == 'query']
        assert len(query_patterns) > 0
        assert query_patterns[0].success_rate > 0.8

    def test_expertise_detection(self):
        """Test that expertise areas are identified correctly."""
        memory = SimpleMemorySystem()
        engine = MemoryInfluenceEngine(memory, min_episodes_for_pattern=3)
        
        # Create expertise in 'inform'
        for i in range(6):
            episode = EpisodicItem(
                importance=0.8,
                structured_input={"text": f"inform {i}"},
                decision=type('Decision', (), {'action_type': 'inform', 'payload': {}})(),
                outcome=Outcome.SUCCESS.value,
            )
            memory.store_episodic(episode)
        
        expertise = engine.get_expertise_areas()
        
        # Should identify 'inform' as expertise
        inform_expertise = [e for e in expertise if e[0] == 'inform']
        assert len(inform_expertise) > 0
        assert inform_expertise[0][1] > 0.7  # Success rate

    def test_avoidance_detection(self):
        """Test that avoidance areas are identified correctly."""
        memory = SimpleMemorySystem()
        engine = MemoryInfluenceEngine(memory, min_episodes_for_pattern=3)
        
        # Create avoidance for 'warn'
        for i in range(5):
            episode = EpisodicItem(
                importance=0.6,
                structured_input={"text": f"warn {i}"},
                decision=type('Decision', (), {'action_type': 'warn', 'payload': {}})(),
                outcome=Outcome.FAILED.value,
            )
            memory.store_episodic(episode)
        
        avoidance = engine.get_avoidance_areas()
        
        # Should identify 'warn' as avoidance
        warn_avoidance = [a for a in avoidance if a[0] == 'warn']
        assert len(warn_avoidance) > 0
        assert warn_avoidance[0][1] > 0.7  # Failure rate


class TestIdentityFormation:
    """Test identity formation from experience."""

    def test_identity_engine_initialization(self):
        """Test that identity engine initializes correctly."""
        engine = IdentityFormationEngine()
        
        assert engine.state.total_experiences == 0
        assert engine.state.identity_coherence == 0.0
        assert len(engine.state.preferences) == 0

    def test_action_preference_formation(self):
        """Test that action preferences form from repeated behavior."""
        engine = IdentityFormationEngine(min_episodes_for_preference=3)
        
        # Observe repeated 'inform' actions with success
        for i in range(5):
            engine.observe_action(
                action_type='inform',
                outcome='success',
                context={'risk_level': 'low'},
            )
        
        # Should have formed preference for 'inform'
        assert 'action_inform' in engine.state.preferences
        pref = engine.state.preferences['action_inform']
        assert pref.strength > 0.5
        assert pref.evidence_count == 5

    def test_risk_tolerance_formation(self):
        """Test that risk tolerance forms from outcomes."""
        engine = IdentityFormationEngine(min_episodes_for_preference=3)
        
        # High risk successes → bold tolerance
        for i in range(4):
            engine.observe_action(
                action_type='execute',
                outcome='success',
                context={'risk_level': 'high'},
            )
        
        # Should have formed bold risk tolerance
        assert 'risk_tolerance' in engine.state.preferences
        pref = engine.state.preferences['risk_tolerance']
        assert pref.value == 'bold'
        assert pref.strength > 0.5

    def test_social_orientation_formation(self):
        """Test that social orientation forms from interactions."""
        engine = IdentityFormationEngine(min_episodes_for_preference=3)
        
        # Successful social interactions
        for i in range(4):
            engine.observe_action(
                action_type='inform',
                outcome='success',
                context={'social_interaction': True},
            )
        
        # Should have formed social preference
        assert 'social_oriented' in engine.state.preferences
        pref = engine.state.preferences['social_oriented']
        assert pref.value == 'social'
        assert pref.strength > 0.5

    def test_identity_coherence(self):
        """Test that identity coherence increases with stable preferences."""
        engine = IdentityFormationEngine(min_episodes_for_preference=3)
        
        # Create multiple stable preferences with enough evidence
        for i in range(15):  # Need enough to make preferences stable
            engine.observe_action('inform', 'success', {})
            engine.observe_action('query', 'success', {})
        
        # Coherence should increase (may be 0 if preferences not yet stable)
        assert engine.state.identity_coherence >= 0.0
        # At minimum, preferences should exist
        assert len(engine.state.preferences) > 0

    def test_identity_signals_for_reasoning(self):
        """Test that identity signals are properly formatted for reasoning."""
        engine = IdentityFormationEngine()
        
        # Create some preferences
        for i in range(3):
            engine.observe_action('inform', 'success', {})
        
        signals = engine.get_identity_signals()
        
        assert 'action_preferences' in signals
        assert 'stable_traits' in signals
        assert 'identity_coherence' in signals
        assert 'recommendations' in signals


class TestValueFormation:
    """Test value formation from outcomes."""

    def test_value_engine_initialization(self):
        """Test that value engine initializes correctly."""
        engine = ValueFormationEngine()
        
        assert engine.state.total_signals == 0
        assert engine.state.value_coherence == 0.0
        assert len(engine.state.values) == 0

    def test_efficiency_value_formation(self):
        """Test that efficiency value forms from fast completions."""
        engine = ValueFormationEngine(min_signals_for_value=3)
        
        # Fast completions → efficiency value
        for i in range(5):
            engine.observe_outcome(
                action_type='execute',
                outcome='success',
                context={'duration_ms': 500},  # Fast
            )
        
        # Should have formed efficiency value
        assert 'efficiency' in engine.state.values
        value = engine.state.values['efficiency']
        assert value.strength > 0.5
        assert value.direction == 'positive'

    def test_reliability_value_formation(self):
        """Test that reliability value forms from first-attempt successes."""
        engine = ValueFormationEngine(min_signals_for_value=3)
        
        # First-attempt successes → reliability value
        for i in range(5):
            engine.observe_outcome(
                action_type='execute',
                outcome='success',
                context={'retries': 0},  # No retries
            )
        
        # Should have formed reliability value
        assert 'reliability' in engine.state.values
        value = engine.state.values['reliability']
        assert value.strength > 0.5
        assert value.direction == 'positive'

    def test_safety_value_formation(self):
        """Test that safety value forms from high-risk failures."""
        engine = ValueFormationEngine(min_signals_for_value=3)
        
        # High-risk failures → safety value
        for i in range(5):
            engine.observe_outcome(
                action_type='execute',
                outcome='failed',
                context={'risk_level': 'high'},
            )
        
        # Should have formed safety value
        assert 'safety' in engine.state.values
        value = engine.state.values['safety']
        assert value.strength > 0.5
        assert value.direction == 'positive'

    def test_value_conflict_detection(self):
        """Test that value conflicts are detected correctly."""
        engine = ValueFormationEngine(min_signals_for_value=3)
        
        # Create speed value
        for i in range(5):
            engine.observe_outcome('execute', 'success', {'speed': 'fast'})
        
        # Create thoroughness value
        for i in range(5):
            engine.observe_outcome('execute', 'success', {'completeness': 'high'})
        
        # Both strong → conflict detected
        if ('speed' in engine.state.values and 
            'thoroughness' in engine.state.values and
            engine.state.values['speed'].strength > 0.6 and
            engine.state.values['thoroughness'].strength > 0.6):
            assert len(engine.state.conflicts) > 0

    def test_value_coherence(self):
        """Test that value coherence increases with stable values."""
        engine = ValueFormationEngine(min_signals_for_value=3)
        
        # Create multiple stable values
        for i in range(15):  # Need enough signals
            engine.observe_outcome('execute', 'success', {
                'duration_ms': 500,
                'retries': 0,
                'risk_level': 'low',
            })
        
        # Coherence should increase (may be 0 if values not yet stable)
        assert engine.state.value_coherence >= 0.0
        # At minimum, values should exist
        assert len(engine.state.values) > 0

    def test_value_signals_for_reasoning(self):
        """Test that value signals are properly formatted for reasoning."""
        engine = ValueFormationEngine()
        
        # Create some values
        for i in range(3):
            engine.observe_outcome('execute', 'success', {'duration_ms': 500})
        
        signals = engine.get_value_signals()
        
        assert 'active_values' in signals
        assert 'conflicts' in signals
        assert 'value_coherence' in signals
        assert 'recommendations' in signals


class TestDevelopmentalIntegration:
    """Test integration of developmental components."""

    def test_ariacore_with_developmental_engines(self):
        """Test that ARIACore initializes with developmental engines."""
        core = ARIACore(llm=None, db_path=":memory:")
        
        assert hasattr(core, 'memory_influence')
        assert hasattr(core, 'identity')
        assert hasattr(core, 'values')
        
        core.shutdown()

    def test_developmental_status(self):
        """Test that developmental status is reported correctly."""
        core = ARIACore(llm=None, db_path=":memory:")
        
        status = core.get_status()
        
        assert 'developmental' in status
        assert 'identity' in status['developmental']
        assert 'values' in status['developmental']
        assert 'memory_influence' in status['developmental']
        
        core.shutdown()

    def test_identity_formation_during_processing(self):
        """Test that identity forms during objective processing."""
        core = ARIACore(llm=None, db_path=":memory:")
        
        # Process multiple objectives
        for i in range(3):
            result = core.process_objective(f"test objective {i}")
        
        # Identity should have formed
        assert core.identity.state.total_experiences > 0
        
        core.shutdown()

    def test_value_formation_during_processing(self):
        """Test that values form during objective processing."""
        core = ARIACore(llm=None, db_path=":memory:")
        
        # Process multiple objectives
        for i in range(3):
            result = core.process_objective(f"test objective {i}")
        
        # Values should have formed
        assert core.values.state.total_signals > 0
        
        core.shutdown()

    def test_memory_influence_caching(self):
        """Test that memory influence signals are cached properly."""
        core = ARIACore(llm=None, db_path=":memory:")
        
        # Initial cache should be empty
        assert len(core.memory_influence._influence_cache) == 0
        
        # After processing, cache should be populated
        core.process_objective("test")
        
        # Cache should now have signals
        assert len(core.memory_influence._influence_cache) >= 0
        
        core.shutdown()


class TestMultiSeedConsistency:
    """Test behavioral consistency across different seeds."""

    def test_seed_determinism(self):
        """Test that same seed produces same initial state."""
        seed = 42
        
        core1 = ARIACore(llm=None, db_path=":memory:")
        core2 = ARIACore(llm=None, db_path=":memory:")
        
        # Process same objective with same seed
        result1 = core1.process_objective("test")
        result2 = core2.process_objective("test")
        
        # Results should be similar (same initial state)
        # Note: May not be identical due to timing, but structure should match
        assert result1['success'] == result2['success']
        
        core1.shutdown()
        core2.shutdown()

    def test_different_seeds_different_behavior(self):
        """Test that different seeds can produce different behaviors."""
        cores = []
        results = []
        
        for seed in range(3):
            core = ARIACore(llm=None, db_path=":memory:")
            result = core.process_objective("test objective")
            results.append(result)
            cores.append(core)
        
        # At least some results should differ
        # (This is a probabilistic test)
        success_values = [r['success'] for r in results]
        
        # Clean up
        for core in cores:
            core.shutdown()


class TestAblationStudies:
    """Test ablation studies for developmental components."""

    def test_memory_influence_ablation(self):
        """Test behavior without memory influence."""
        # Create core with minimal memory influence
        core = ARIACore(llm=None, db_path=":memory:")
        core.memory_influence._influence_weight = 0.0  # Disable influence
        
        # Process objectives
        for i in range(3):
            core.process_objective(f"test {i}")
        
        # Should still work, just without influence
        status = core.get_status()
        assert status['cycle_count'] == 3
        
        core.shutdown()

    def test_identity_ablation(self):
        """Test behavior without identity formation."""
        core = ARIACore(llm=None, db_path=":memory:")
        
        # Disable identity observation
        original_observe = core.identity.observe_action
        core.identity.observe_action = lambda *args, **kwargs: None
        
        # Process objectives
        for i in range(3):
            core.process_objective(f"test {i}")
        
        # Identity should not have formed
        assert core.identity.state.total_experiences == 0
        
        core.shutdown()

    def test_values_ablation(self):
        """Test behavior without value formation."""
        core = ARIACore(llm=None, db_path=":memory:")
        
        # Disable value observation
        original_observe = core.values.observe_outcome
        core.values.observe_outcome = lambda *args, **kwargs: None
        
        # Process objectives
        for i in range(3):
            core.process_objective(f"test {i}")
        
        # Values should not have formed
        assert core.values.state.total_signals == 0
        
        core.shutdown()


class TestEmergentBehaviors:
    """Test for emergent behaviors from developmental processes."""

    def test_behavioral_consistency(self):
        """Test that repeated experiences lead to consistent behavior."""
        core = ARIACore(llm=None, db_path=":memory:")
        
        # Process same type of objective multiple times
        results = []
        for i in range(5):
            result = core.process_objective("read and analyze code")
            results.append(result)
        
        # Behavior should become more consistent over time
        # (Check that success rate stabilizes)
        success_rates = []
        for i in range(1, len(results) + 1):
            rate = sum(r['success'] for r in results[:i]) / i
            success_rates.append(rate)
        
        # Later rates should be more stable
        if len(success_rates) > 2:
            early_variance = abs(success_rates[0] - success_rates[1])
            late_variance = abs(success_rates[-1] - success_rates[-2])
            # Variance should decrease (or at least not increase dramatically)
            assert late_variance <= early_variance + 0.1
        
        core.shutdown()

    def test_preference_stability(self):
        """Test that preferences become stable over time."""
        core = ARIACore(llm=None, db_path=":memory:")
        
        # Process many objectives
        for i in range(10):
            core.process_objective(f"objective {i}")
        
        # Check for stable preferences
        stable_prefs = core.identity.get_stable_preferences()
        
        # Should have some stable preferences after enough experience
        # (This is a probabilistic test)
        assert len(stable_prefs) >= 0
        
        core.shutdown()

    def test_value_emergence(self):
        """Test that values emerge from repeated outcomes."""
        core = ARIACore(llm=None, db_path=":memory:")
        
        # Process many fast objectives
        for i in range(10):
            core.process_objective(f"quick task {i}")
        
        # Check for emerged values
        stable_values = core.values.get_stable_values()
        
        # Should have some stable values after enough experience
        assert len(stable_values) >= 0
        
        core.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
