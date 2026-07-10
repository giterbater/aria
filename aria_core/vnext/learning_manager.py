# aria_core/vnext/learning_manager.py
"""
Learning Manager — decides how ARIA learns from every experience.

The LearningManager never directly modifies systems.
It only produces learning actions.

Pipeline:
Experience → Evaluate → Score Importance → Plan Actions → Return Plan
"""

from __future__ import annotations

import datetime
from typing import Optional, Protocol, runtime_checkable

from .models import (
    Experience,
    ImportanceScore,
    LearningAction,
    LearningActionPlan,
    EmotionalState,
    MemoryEntry,
)


@runtime_checkable
class MemoryStore(Protocol):
    """Protocol for memory systems that LearningManager can query."""
    
    def search_similar(self, content: Any, limit: int = 5) -> list[MemoryEntry]: ...
    def get_recent(self, limit: int = 10) -> list[MemoryEntry]: ...
    def count(self) -> int: ...


class ImportanceScorer:
    """Scores importance of experiences based on multiple factors."""
    
    def __init__(
        self,
        novelty_weight: float = 0.25,
        reward_weight: float = 0.20,
        emotional_weight: float = 0.20,
        prediction_error_weight: float = 0.15,
        uncertainty_weight: float = 0.10,
        repetition_penalty: float = 0.10,
    ):
        self._novelty_weight = novelty_weight
        self._reward_weight = reward_weight
        self._emotional_weight = emotional_weight
        self._prediction_error_weight = prediction_error_weight
        self._uncertainty_weight = uncertainty_weight
        self._repetition_penalty = repetition_penalty
    
    def score(
        self,
        experience: Experience,
        similar_count: int = 0,
        total_memories: int = 0,
    ) -> ImportanceScore:
        """
        Score the importance of an experience.
        
        Args:
            experience: The experience to score
            similar_count: Number of similar memories found
            total_memories: Total memories in store
        """
        reasons = []
        score = 0.0
        
        # 1. Novelty (inverse of similarity)
        novelty = 1.0 - min(1.0, similar_count / 5.0)
        score += novelty * self._novelty_weight
        if novelty > 0.7:
            reasons.append("high novelty")
        
        # 2. Reward (absolute value of reward)
        reward_score = abs(experience.reward)
        score += reward_score * self._reward_weight
        if reward_score > 0.7:
            reasons.append("strong reward signal")
        
        # 3. Emotional intensity
        emotional_score = experience.emotional_intensity
        score += emotional_score * self._emotional_weight
        if emotional_score > 0.7:
            reasons.append("high emotional intensity")
        
        # 4. Prediction error (unexpected outcomes)
        prediction_error = abs(experience.reward) if experience.success else 0.5
        score += prediction_error * self._prediction_error_weight
        if prediction_error > 0.6:
            reasons.append("unexpected outcome")
        
        # 5. Uncertainty (low confidence = high uncertainty)
        uncertainty = 1.0 - experience.confidence
        score += uncertainty * self._uncertainty_weight
        if uncertainty > 0.6:
            reasons.append("high uncertainty")
        
        # 6. Repetition penalty (similar experiences reduce importance)
        if similar_count > 3:
            repetition_deduction = min(0.3, similar_count * 0.05)
            score -= repetition_deduction
            reasons.append(f"repetition penalty ({similar_count} similar)")
        
        # Clamp score
        score = max(0.0, min(1.0, score))
        
        # Calculate confidence in the score
        confidence = 0.5
        if total_memories > 10:
            confidence += 0.2
        if similar_count > 0:
            confidence += 0.1
        
        return ImportanceScore(
            score=score,
            reasons=reasons,
            confidence=min(1.0, confidence),
        )


class LearningManager:
    """
    Decides how ARIA learns from every experience.
    
    The LearningManager never directly modifies systems.
    It only produces learning actions.
    
    Usage:
        manager = LearningManager(memory_store=memory)
        plan = manager.evaluate(experience)
        
        for action in plan.actions:
            if action == LearningAction.STORE_EPISODIC:
                memory.store(experience)
            elif action == LearningAction.UPDATE_EMOTIONAL_STATE:
                emotions.update(experience)
    """
    
    def __init__(
        self,
        memory_store: Optional[MemoryStore] = None,
        emotional_state: Optional[EmotionalState] = None,
        importance_threshold: float = 0.5,
        critical_threshold: float = 0.8,
    ):
        self._memory_store = memory_store
        self._emotional_state = emotional_state or EmotionalState()
        self._importance_threshold = importance_threshold
        self._critical_threshold = critical_threshold
        self._scorer = ImportanceScorer()
        
        # Statistics
        self._evaluations_count = 0
        self._actions_planned = 0
    
    def evaluate(self, experience: Experience) -> LearningActionPlan:
        """
        Evaluate an experience and produce a learning action plan.
        
        This is the main entry point.
        """
        self._evaluations_count += 1
        
        # 1. Find similar memories
        similar_count = 0
        if self._memory_store:
            try:
                similar = self._memory_store.search_similar(
                    experience.action + " " + experience.result,
                    limit=5,
                )
                similar_count = len(similar)
            except Exception:
                pass
        
        # 2. Score importance
        total_memories = 0
        if self._memory_store:
            try:
                total_memories = self._memory_store.count()
            except Exception:
                pass
        
        importance = self._scorer.score(
            experience,
            similar_count=similar_count,
            total_memories=total_memories,
        )
        
        # 3. Plan actions based on importance and context
        actions = self._plan_actions(experience, importance, similar_count)
        
        # 4. Generate reasoning
        reasoning = self._generate_reasoning(experience, importance, actions)
        
        plan = LearningActionPlan(
            experience_id=experience.id,
            importance=importance,
            actions=actions,
            reasoning=reasoning,
        )
        
        self._actions_planned += len(actions)
        
        return plan
    
    def _plan_actions(
        self,
        experience: Experience,
        importance: ImportanceScore,
        similar_count: int,
    ) -> list[LearningAction]:
        """Plan learning actions based on importance and context."""
        actions = []
        
        # If not important enough, ignore
        if importance.score < self._importance_threshold:
            actions.append(LearningAction.IGNORE)
            return actions
        
        # Always update emotional state
        actions.append(LearningAction.UPDATE_EMOTIONAL_STATE)
        
        # Store in episodic memory if important enough
        if importance.score >= 0.3:
            actions.append(LearningAction.STORE_EPISODIC)
        
        # Strengthen semantic memory for repeated patterns
        if similar_count >= 3:
            actions.append(LearningAction.STRENGTHEN_SEMANTIC)
        
        # Update identity for significant experiences
        if importance.score >= 0.6 and experience.emotional_intensity > 0.5:
            actions.append(LearningAction.UPDATE_IDENTITY)
        
        # Update values for reward-based experiences
        if abs(experience.reward) > 0.5:
            actions.append(LearningAction.UPDATE_VALUES)
        
        # Schedule consolidation for critical experiences
        if importance.score >= self._critical_threshold:
            actions.append(LearningAction.SCHEDULE_CONSOLIDATION)
        
        # Trigger retraining for very important discoveries
        if importance.score >= 0.9 and experience.experience_type.value == "discovery":
            actions.append(LearningAction.TRIGGER_RETRAINING)
        
        return actions
    
    def _generate_reasoning(
        self,
        experience: Experience,
        importance: ImportanceScore,
        actions: list[LearningAction],
    ) -> str:
        """Generate human-readable reasoning for the action plan."""
        parts = [
            f"Experience {experience.id}: {experience.action} → {experience.result}",
            f"Importance: {importance.score:.2f} ({', '.join(importance.reasons) if importance.reasons else 'no notable factors'})",
            f"Actions: {', '.join(a.value for a in actions)}",
        ]
        
        if importance.is_critical:
            parts.append("CRITICAL: This experience requires immediate attention.")
        elif importance.is_important:
            parts.append("IMPORTANT: This experience should be stored and learned from.")
        
        return " | ".join(parts)
    
    def get_statistics(self) -> dict[str, int]:
        """Get learning manager statistics."""
        return {
            "evaluations": self._evaluations_count,
            "actions_planned": self._actions_planned,
        }
