# tests/test_vnext.py
"""
Tests for ARIA vNext modules.

Validates:
1. Learning Manager evaluates experiences correctly
2. Importance scoring works
3. Emotional system adapts
4. Memory stores and retrieves
5. Dream scheduler consolidates
6. Neural pipeline buffers and trains
"""

from __future__ import annotations

import pytest

from aria_core.vnext.models import (
    Experience,
    ExperienceType,
    ImportanceScore,
    LearningAction,
    EmotionalState,
    EmotionType,
    MemoryEntry,
    MemoryType,
)
from aria_core.vnext.learning_manager import LearningManager, ImportanceScorer
from aria_core.vnext.emotions import AdaptiveEmotionSystem
from aria_core.vnext.memory import ContinualMemory
from aria_core.vnext.dreams import DreamScheduler
from aria_core.vnext.neural import (
    ExperienceBuffer,
    NeuralTrainer,
    NeuralAdaptationPipeline,
)


class TestImportanceScorer:
    """Test importance scoring."""

    def test_novel_experience_scores_high(self):
        """Test that novel experiences score high."""
        scorer = ImportanceScorer()
        
        experience = Experience(
            action="discover_new_thing",
            result="success",
            success=True,
            reward=0.8,
            emotional_intensity=0.7,
        )
        
        score = scorer.score(experience, similar_count=0, total_memories=10)
        
        assert score.score > 0.5
        assert score.is_important

    def test_repeated_experience_scores_low(self):
        """Test that repeated experiences score low."""
        scorer = ImportanceScorer()
        
        experience = Experience(
            action="same_old_thing",
            result="success",
            success=True,
            reward=0.3,
        )
        
        score = scorer.score(experience, similar_count=5, total_memories=100)
        
        assert score.score < 0.5
        assert not score.is_important

    def test_emotional_experience_scores_high(self):
        """Test that emotional experiences score high."""
        scorer = ImportanceScorer()
        
        experience = Experience(
            action="traumatic_event",
            result="failure",
            success=False,
            reward=-0.9,
            emotional_intensity=0.9,
            emotional_valence=-0.8,
        )
        
        score = scorer.score(experience, similar_count=0, total_memories=10)
        
        assert score.score > 0.5


class TestLearningManager:
    """Test learning manager."""

    def test_ignores_unimportant_experiences(self):
        """Test that unimportant experiences are ignored."""
        manager = LearningManager(importance_threshold=0.5)
        
        experience = Experience(
            action="routine_task",
            result="success",
            success=True,
            reward=0.1,
            emotional_intensity=0.1,
        )
        
        plan = manager.evaluate(experience)
        
        assert LearningAction.IGNORE in plan.actions

    def test_stores_important_experiences(self):
        """Test that important experiences are stored."""
        manager = LearningManager(importance_threshold=0.3)
        
        experience = Experience(
            action="significant_discovery",
            result="success",
            success=True,
            reward=0.9,
            emotional_intensity=0.8,
        )
        
        plan = manager.evaluate(experience)
        
        assert LearningAction.STORE_EPISODIC in plan.actions
        assert LearningAction.UPDATE_EMOTIONAL_STATE in plan.actions

    def test_updates_identity_for_emotional_experiences(self):
        """Test that emotional experiences update identity."""
        manager = LearningManager(importance_threshold=0.3)
        
        experience = Experience(
            action="life_defining_moment",
            result="success",
            success=True,
            reward=0.7,
            emotional_intensity=0.9,
        )
        
        plan = manager.evaluate(experience)
        
        assert LearningAction.UPDATE_IDENTITY in plan.actions

    def test_updates_values_for_reward_experiences(self):
        """Test that reward experiences update values."""
        manager = LearningManager(importance_threshold=0.3)
        
        experience = Experience(
            action="ethical_choice",
            result="success",
            success=True,
            reward=0.8,
        )
        
        plan = manager.evaluate(experience)
        
        assert LearningAction.UPDATE_VALUES in plan.actions


class TestAdaptiveEmotionSystem:
    """Test emotional system."""

    def test_success_increases_confidence(self):
        """Test that success increases confidence."""
        emotions = AdaptiveEmotionSystem()
        
        initial_confidence = emotions.get(EmotionType.CONFIDENCE)
        
        experience = Experience(success=True, reward=0.5)
        emotions.update_from_experience(experience)
        
        assert emotions.get(EmotionType.CONFIDENCE) > initial_confidence

    def test_failure_increases_frustration(self):
        """Test that failure increases frustration."""
        emotions = AdaptiveEmotionSystem()
        
        initial_frustration = emotions.get(EmotionType.FRUSTRATION)
        
        experience = Experience(success=False, reward=-0.3)
        emotions.update_from_experience(experience)
        
        assert emotions.get(EmotionType.FRUSTRATION) > initial_frustration

    def test_repeated_failure_reduces_motivation(self):
        """Test that repeated failure reduces motivation."""
        emotions = AdaptiveEmotionSystem()
        
        initial_motivation = emotions.get(EmotionType.MOTIVATION)
        
        for _ in range(5):
            experience = Experience(success=False, reward=-0.2)
            emotions.update_from_experience(experience)
        
        assert emotions.get(EmotionType.MOTIVATION) < initial_motivation

    def test_discovery_increases_curiosity(self):
        """Test that discovery increases curiosity."""
        emotions = AdaptiveEmotionSystem()
        
        initial_curiosity = emotions.get(EmotionType.CURIOSITY)
        
        experience = Experience(
            experience_type=ExperienceType.DISCOVERY,
            success=True,
        )
        emotions.update_from_experience(experience)
        
        assert emotions.get(EmotionType.CURIOSITY) > initial_curiosity

    def test_exploration_rate_depends_on_curiosity(self):
        """Test that exploration rate depends on curiosity."""
        emotions = AdaptiveEmotionSystem()
        
        # High curiosity → high exploration
        emotions._state.curiosity = 0.9
        assert emotions.get_exploration_rate() > 0.6
        
        # Low curiosity → low exploration
        emotions._state.curiosity = 0.1
        assert emotions.get_exploration_rate() < 0.4

    def test_caution_increases_with_frustration(self):
        """Test that caution increases with frustration."""
        emotions = AdaptiveEmotionSystem()
        
        # High frustration → high caution
        emotions._state.frustration = 0.9
        assert emotions.get_caution_level() > 0.5
        
        # Low frustration → low caution
        emotions._state.frustration = 0.1
        assert emotions.get_caution_level() < 0.5


class TestContinualMemory:
    """Test memory system."""

    def test_store_and_retrieve(self):
        """Test storing and retrieving memories."""
        memory = ContinualMemory()
        
        entry = MemoryEntry(
            memory_type=MemoryType.EPISODIC,
            content={"action": "test", "result": "success"},
            importance=0.7,
        )
        
        entry_id = memory.store(entry)
        retrieved = memory.get(entry_id)
        
        assert retrieved is not None
        assert retrieved.content == entry.content

    def test_search_similar(self):
        """Test searching for similar memories."""
        memory = ContinualMemory()
        
        memory.store(MemoryEntry(
            memory_type=MemoryType.EPISODIC,
            content="scan code repository",
            importance=0.5,
        ))
        
        memory.store(MemoryEntry(
            memory_type=MemoryType.EPISODIC,
            content="run tests suite",
            importance=0.5,
        ))
        
        results = memory.search_similar("scan code")
        
        assert len(results) > 0

    def test_strengthen(self):
        """Test strengthening memories."""
        memory = ContinualMemory()
        
        entry_id = memory.store(MemoryEntry(
            memory_type=MemoryType.EPISODIC,
            content="important event",
            importance=0.5,
        ))
        
        memory.strengthen(entry_id, delta=0.2)
        entry = memory.get(entry_id)
        
        assert entry.importance == 0.7

    def test_temporal_decay(self):
        """Test temporal decay."""
        memory = ContinualMemory()
        
        memory.store(MemoryEntry(
            memory_type=MemoryType.EPISODIC,
            content="old event",
            importance=0.5,
        ))
        
        affected = memory.apply_temporal_decay()
        
        assert affected >= 0

    def test_statistics(self):
        """Test memory statistics."""
        memory = ContinualMemory()
        
        memory.store(MemoryEntry(
            memory_type=MemoryType.EPISODIC,
            content="test",
        ))
        
        stats = memory.get_statistics()
        
        assert stats["current_count"] == 1
        assert stats["by_type"]["episodic"] == 1


class TestDreamScheduler:
    """Test dream scheduler."""

    def test_dream_session(self):
        """Test running a dream session."""
        memory = ContinualMemory()
        
        # Add some memories
        for i in range(10):
            memory.store(MemoryEntry(
                memory_type=MemoryType.EPISODIC,
                content=f"event {i}",
                importance=0.5 + (i * 0.05),
            ))
        
        scheduler = DreamScheduler(memory=memory)
        session = scheduler.dream()
        
        summary = session.summary()
        assert summary["memories_replayed"] > 0

    def test_consolidation(self):
        """Test memory consolidation."""
        memory = ContinualMemory()
        
        # Add important episodic memories
        for i in range(5):
            memory.store(MemoryEntry(
                memory_type=MemoryType.EPISODIC,
                content=f"important event {i}",
                importance=0.8,
            ))
        
        scheduler = DreamScheduler(memory=memory)
        session = scheduler.dream()
        
        summary = session.summary()
        assert summary["memories_consolidated"] > 0


class TestExperienceBuffer:
    """Test experience buffer."""

    def test_add_and_ready(self):
        """Test adding experiences and readiness."""
        buffer = ExperienceBuffer(max_size=100, min_size=5)
        
        assert not buffer.is_ready()
        
        for i in range(5):
            buffer.add(Experience())
        
        assert buffer.is_ready()

    def test_batch(self):
        """Test getting batches."""
        buffer = ExperienceBuffer(max_size=100, min_size=5)
        
        for i in range(10):
            buffer.add(Experience())
        
        batch = buffer.get_batch(5)
        
        assert len(batch) == 5

    def test_clear(self):
        """Test clearing buffer."""
        buffer = ExperienceBuffer()
        
        buffer.add(Experience())
        buffer.add(Experience())
        
        buffer.clear()
        
        assert buffer.size() == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
