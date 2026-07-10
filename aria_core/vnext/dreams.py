# aria_core/vnext/dreams.py
"""
Offline Consolidation ("Dreaming") — background learning.

When idle:
- Replay important experiences
- Consolidate memories
- Discover patterns
- Strengthen associations
- Compress redundant memories
- Generate hypothetical experiences

Dreaming never directly affects reasoning.
Instead it updates long-term memory.
"""

from __future__ import annotations

import datetime
from typing import Optional, Protocol, runtime_checkable

from .models import MemoryEntry, MemoryType, Experience


@runtime_checkable
class MemorySystem(Protocol):
    """Protocol for memory systems that dreaming can update."""
    
    def store(self, entry: MemoryEntry) -> str: ...
    def strengthen(self, entry_id: str, delta: float) -> bool: ...
    def get_recent(self, limit: int) -> list[MemoryEntry]: ...
    def count(self) -> int: ...
    def apply_temporal_decay(self) -> int: ...
    def forget(self, max_age_days: int, importance_threshold: float) -> int: ...


class DreamSession:
    """A single dream session."""
    
    def __init__(self):
        self.start_time = datetime.datetime.now()
        self.memories_replayed = 0
        self.memories_consolidated = 0
        self.memories_strengthened = 0
        self.patterns_discovered = 0
        self.hypotheticals_generated = 0
        self.decay_applied = 0
        self.forgetting_applied = 0
    
    def summary(self) -> dict:
        """Get summary of dream session."""
        duration = (datetime.datetime.now() - self.start_time).total_seconds()
        return {
            "duration_seconds": duration,
            "memories_replayed": self.memories_replayed,
            "memories_consolidated": self.memories_consolidated,
            "memories_strengthened": self.memories_strengthened,
            "patterns_discovered": self.patterns_discovered,
            "hypotheticals_generated": self.hypotheticals_generated,
            "decay_applied": self.decay_applied,
            "forgetting_applied": self.forgetting_applied,
        }


class DreamScheduler:
    """
    Manages offline consolidation ("dreaming").
    
    Usage:
        scheduler = DreamScheduler(memory=memory_system)
        
        # Run a dream session
        session = scheduler.dream()
        print(session.summary())
    """
    
    def __init__(
        self,
        memory: MemorySystem,
        consolidation_threshold: float = 0.7,
        strengthen_threshold: float = 0.5,
        max_replay: int = 50,
    ):
        self._memory = memory
        self._consolidation_threshold = consolidation_threshold
        self._strengthen_threshold = strengthen_threshold
        self._max_replay = max_replay
        
        # History
        self._sessions: list[DreamSession] = []
    
    def dream(self) -> DreamSession:
        """Run a dream session."""
        session = DreamSession()
        
        # 1. Replay important memories
        self._replay_memories(session)
        
        # 2. Consolidate episodic → semantic
        self._consolidate_memories(session)
        
        # 3. Strengthen frequently accessed memories
        self._strengthen_memories(session)
        
        # 4. Discover patterns
        self._discover_patterns(session)
        
        # 5. Apply temporal decay
        self._apply_decay(session)
        
        # 6. Forget old, unimportant memories
        self._forget_old(session)
        
        self._sessions.append(session)
        
        return session
    
    def _replay_memories(self, session: DreamSession) -> None:
        """Replay important memories to strengthen them."""
        recent = self._memory.get_recent(limit=self._max_replay)
        
        for entry in recent:
            if entry.importance >= self._strengthen_threshold:
                # Strengthen important memories
                self._memory.strengthen(entry.id, delta=0.02)
                session.memories_replayed += 1
                session.memories_strengthened += 1
    
    def _consolidate_memories(self, session: DreamSession) -> None:
        """Consolidate episodic memories into semantic memory."""
        episodic = self._memory.get_recent(limit=100)
        
        for entry in episodic:
            if entry.importance >= self._consolidation_threshold:
                # Create semantic memory from episodic
                semantic = MemoryEntry(
                    memory_type=MemoryType.SEMANTIC,
                    content=entry.content,
                    importance=entry.importance,
                    confidence=entry.confidence,
                    source_experience_id=entry.id,
                )
                self._memory.store(semantic)
                session.memories_consolidated += 1
    
    def _strengthen_memories(self, session: DreamSession) -> None:
        """Strengthen frequently accessed memories."""
        # This would use access patterns in a real implementation
        # For now, just strengthen recent memories
        recent = self._memory.get_recent(limit=20)
        
        for entry in recent:
            if entry.access_count > 3:
                self._memory.strengthen(entry.id, delta=0.01)
                session.memories_strengthened += 1
    
    def _discover_patterns(self, session: DreamSession) -> None:
        """Discover patterns in memories."""
        # This would use more sophisticated pattern detection
        # For now, just count patterns
        recent = self._memory.get_recent(limit=50)
        
        # Simple pattern: count repeated action types
        action_counts: dict[str, int] = {}
        for entry in recent:
            if isinstance(entry.content, dict):
                action = entry.content.get("action", "")
                if action:
                    action_counts[action] = action_counts.get(action, 0) + 1
        
        # Discover patterns (actions repeated 3+ times)
        for action, count in action_counts.items():
            if count >= 3:
                session.patterns_discovered += 1
    
    def _apply_decay(self, session: DreamSession) -> None:
        """Apply temporal decay to all memories."""
        session.decay_applied = self._memory.apply_temporal_decay()
    
    def _forget_old(self, session: DreamSession) -> None:
        """Forget old, unimportant memories."""
        session.forgetting_applied = self._memory.forget(
            max_age_days=30,
            importance_threshold=0.2,
        )
    
    def get_history(self) -> list[dict]:
        """Get history of dream sessions."""
        return [session.summary() for session in self._sessions]
    
    def get_average_duration(self) -> float:
        """Get average dream session duration."""
        if not self._sessions:
            return 0.0
        
        durations = []
        for session in self._sessions:
            duration = (datetime.datetime.now() - session.start_time).total_seconds()
            durations.append(duration)
        
        return sum(durations) / len(durations)
