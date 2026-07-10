# aria_core/vnext/emotions.py
"""
Adaptive Emotion System — replaces static emotions with adaptive state.

Emotions evolve continuously based on experience.
Emotions directly influence reasoning, planning, and memory.

Example:
High curiosity → Explore more hypotheses
High frustration → Become more cautious
High confidence → Trust internal knowledge more
Low confidence → Verify using memory and internet
"""

from __future__ import annotations

import datetime
from typing import Optional

from .models import EmotionalState, EmotionType, Experience


class AdaptiveEmotionSystem:
    """
    Manages adaptive emotional state.
    
    Emotions are not presets — they emerge from experience.
    
    Usage:
        emotions = AdaptiveEmotionSystem()
        emotions.update_from_experience(experience)
        
        # Use emotions to influence behavior
        if emotions.get(EmotionType.CURIOSITY) > 0.7:
            # Explore more
            pass
    """
    
    def __init__(
        self,
        learning_rate: float = 0.1,
        decay_rate: float = 0.02,
        frustration_threshold: int = 3,
    ):
        self._learning_rate = learning_rate
        self._decay_rate = decay_rate
        self._frustration_threshold = frustration_threshold
        
        self._state = EmotionalState()
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        
        # History for pattern detection
        self._recent_rewards: list[float] = []
        self._recent_confidence: list[float] = []
    
    @property
    def state(self) -> EmotionalState:
        """Get current emotional state."""
        return self._state
    
    def get(self, emotion: EmotionType) -> float:
        """Get value for an emotion type."""
        return self._state.get(emotion)
    
    def update_from_experience(self, experience: Experience) -> None:
        """Update emotional state based on an experience."""
        
        # Update based on outcome
        if experience.success:
            self._consecutive_successes += 1
            self._consecutive_failures = 0
            
            # Success increases confidence
            self._adjust(EmotionType.CONFIDENCE, 0.05)
            
            # Success reduces frustration
            self._adjust(EmotionType.FRUSTRATION, -0.1)
            
            # Success increases motivation slightly
            self._adjust(EmotionType.MOTIVATION, 0.03)
        else:
            self._consecutive_failures += 1
            self._consecutive_successes = 0
            
            # Failure decreases confidence
            self._adjust(EmotionType.CONFIDENCE, -0.08)
            
            # Failure increases frustration
            self._adjust(EmotionType.FRUSTRATION, 0.1)
            
            # Repeated failure reduces motivation
            if self._consecutive_failures >= self._frustration_threshold:
                self._adjust(EmotionType.MOTIVATION, -0.1)
        
        # Update based on emotional content
        if experience.emotional_intensity > 0.5:
            # Strong emotional experiences affect attachment
            if experience.emotional_valence > 0:
                self._adjust(EmotionType.ATTACHMENT, 0.05)
            else:
                self._adjust(EmotionType.STRESS, 0.1)
        
        # Update curiosity based on novelty
        if experience.experience_type.value == "discovery":
            self._adjust(EmotionType.CURIOSITY, 0.15)
        
        # Update fatigue (increases with each experience)
        self._adjust(EmotionType.FATIGUE, 0.02)
        
        # Track recent patterns
        self._recent_rewards.append(experience.reward)
        if len(self._recent_rewards) > 20:
            self._recent_rewards.pop(0)
        
        self._recent_confidence.append(experience.confidence)
        if len(self._recent_confidence) > 20:
            self._recent_confidence.pop(0)
        
        # Apply natural decay
        self._apply_decay()
        
        # Update timestamp
        self._state.timestamp = datetime.datetime.now()
    
    def get_exploration_rate(self) -> float:
        """
        Get exploration rate based on emotional state.
        
        High curiosity → higher exploration
        High frustration → lower exploration
        """
        curiosity = self.get(EmotionType.CURIOSITY)
        frustration = self.get(EmotionType.FRUSTRATION)
        
        return max(0.1, min(0.9, curiosity * 0.7 + (1 - frustration) * 0.3))
    
    def get_caution_level(self) -> float:
        """
        Get caution level based on emotional state.
        
        High frustration → higher caution
        High confidence → lower caution
        """
        frustration = self.get(EmotionType.FRUSTRATION)
        confidence = self.get(EmotionType.CONFIDENCE)
        
        return max(0.1, min(0.9, frustration * 0.6 + (1 - confidence) * 0.4))
    
    def get_reasoning_depth(self) -> int:
        """
        Get reasoning depth based on emotional state.
        
        High curiosity → deeper reasoning
        High stress → shallower reasoning
        """
        curiosity = self.get(EmotionType.CURIOSITY)
        stress = self.get(EmotionType.STRESS)
        
        # 1 = shallow, 5 = deep
        depth = 1 + int((curiosity * 0.7 + (1 - stress) * 0.3) * 4)
        return max(1, min(5, depth))
    
    def should_verify_with_memory(self) -> bool:
        """Check if we should verify using memory."""
        confidence = self.get(EmotionType.CONFIDENCE)
        return confidence < 0.5
    
    def should_use_internet(self) -> bool:
        """Check if we should use internet for verification."""
        confidence = self.get(EmotionType.CONFIDENCE)
        uncertainty = 1.0 - confidence
        return uncertainty > 0.6
    
    def get_memory_consolidation_priority(self) -> float:
        """
        Get priority for memory consolidation.
        
        High motivation → higher priority
        High fatigue → lower priority
        """
        motivation = self.get(EmotionType.MOTIVATION)
        fatigue = self.get(EmotionType.FATIGUE)
        
        return max(0.0, min(1.0, motivation * 0.7 + (1 - fatigue) * 0.3))
    
    def reset_daily(self) -> None:
        """Reset daily emotions (call at start of each day)."""
        self._adjust(EmotionType.FATIGUE, -0.3)
        self._adjust(EmotionType.STRESS, -0.2)
        self._consecutive_failures = 0
        self._consecutive_successes = 0
    
    def _adjust(self, emotion: EmotionType, delta: float) -> None:
        """Adjust an emotion value."""
        current = self.get(emotion)
        new_value = current + delta * self._learning_rate
        self._state.set(emotion, new_value)
    
    def _apply_decay(self) -> None:
        """Apply natural decay to all emotions."""
        for emotion in EmotionType:
            current = self.get(emotion)
            if current > 0.5:
                # Decay towards neutral
                decay = self._decay_rate * (current - 0.5)
                self._state.set(emotion, current - decay)
            elif current < 0.5:
                # Decay towards neutral
                decay = self._decay_rate * (0.5 - current)
                self._state.set(emotion, current + decay)
    
    def get_summary(self) -> str:
        """Get human-readable summary of emotional state."""
        lines = [
            f"Curiosity: {self.get(EmotionType.CURIOSITY):.2f}",
            f"Confidence: {self.get(EmotionType.CONFIDENCE):.2f}",
            f"Frustration: {self.get(EmotionType.FRUSTRATION):.2f}",
            f"Motivation: {self.get(EmotionType.MOTIVATION):.2f}",
            f"Fatigue: {self.get(EmotionType.FATIGUE):.2f}",
            f"Attachment: {self.get(EmotionType.ATTACHMENT):.2f}",
            f"Stress: {self.get(EmotionType.STRESS):.2f}",
            f"Exploration rate: {self.get_exploration_rate():.2f}",
            f"Caution level: {self.get_caution_level():.2f}",
            f"Reasoning depth: {self.get_reasoning_depth()}",
        ]
        return "\n".join(lines)
