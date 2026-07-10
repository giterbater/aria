# aria_core/vnext/memory.py
"""
Continual Memory — the primary learning system.

Memory types:
- Episodic: what happened
- Semantic: what I know
- Procedural: how to do things
- Identity: who I am
- Value: what I care about
- Perception: what I've seen

Supports:
- Similarity search
- Forgetting policies
- Reinforcement
- Confidence updates
- Temporal decay
- Memory strengthening
"""

from __future__ import annotations

import datetime
import math
from typing import Any, Optional

from .models import MemoryEntry, MemoryType, Experience


class ContinualMemory:
    """
    Memory system that grows and evolves with experience.
    
    Usage:
        memory = ContinualMemory()
        
        # Store memories
        memory.store(MemoryEntry(
            memory_type=MemoryType.EPISODIC,
            content={"action": "scan", "result": "success"},
            importance=0.7,
        ))
        
        # Search
        results = memory.search_similar("scan code")
        
        # Strengthen
        memory.strengthen(memory_id, delta=0.1)
    """
    
    def __init__(
        self,
        max_entries: int = 10000,
        decay_rate: float = 0.01,
        reinforcement_boost: float = 0.1,
    ):
        self._max_entries = max_entries
        self._decay_rate = decay_rate
        self._reinforcement_boost = reinforcement_boost
        
        # Memory stores by type
        self._stores: dict[MemoryType, list[MemoryEntry]] = {
            mt: [] for mt in MemoryType
        }
        
        # Index for fast lookup
        self._id_index: dict[str, MemoryEntry] = {}
        
        # Statistics
        self._total_stored = 0
        self._total_forgotten = 0
    
    def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry. Returns the entry ID."""
        # Add to appropriate store
        self._stores[entry.memory_type].append(entry)
        
        # Add to index
        self._id_index[entry.id] = entry
        
        self._total_stored += 1
        
        # Apply forgetting if over capacity
        if self._total_entries() > self._max_entries:
            self._forget_least_important()
        
        return entry.id
    
    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """Get a memory by ID."""
        entry = self._id_index.get(entry_id)
        if entry:
            # Update access count
            entry.access_count += 1
            entry.last_accessed = datetime.datetime.now()
        return entry
    
    def search_similar(
        self,
        content: str,
        memory_type: Optional[MemoryType] = None,
        limit: int = 5,
    ) -> list[MemoryEntry]:
        """Search for similar memories."""
        content_lower = content.lower()
        content_tokens = set(content_lower.split())
        
        candidates = []
        
        # Search in specified type or all types
        stores = [memory_type] if memory_type else list(MemoryType)
        
        for mt in stores:
            for entry in self._stores.get(mt, []):
                # Simple token overlap similarity
                entry_text = self._entry_to_text(entry)
                entry_tokens = set(entry_text.lower().split())
                
                if not content_tokens or not entry_tokens:
                    continue
                
                overlap = len(content_tokens & entry_tokens)
                similarity = overlap / max(len(content_tokens | entry_tokens), 1)
                
                # Weight by importance and recency
                recency_weight = self._recency_weight(entry)
                score = similarity * entry.importance * recency_weight
                
                if score > 0.01:
                    candidates.append((score, entry))
        
        # Sort by score
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        return [entry for _, entry in candidates[:limit]]
    
    def get_recent(
        self,
        memory_type: Optional[MemoryType] = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Get recent memories."""
        stores = [memory_type] if memory_type else list(MemoryType)
        
        all_entries = []
        for mt in stores:
            all_entries.extend(self._stores.get(mt, []))
        
        # Sort by timestamp
        all_entries.sort(key=lambda e: e.timestamp, reverse=True)
        
        return all_entries[:limit]
    
    def strengthen(self, entry_id: str, delta: float = 0.1) -> bool:
        """Strengthen a memory's importance."""
        entry = self._id_index.get(entry_id)
        if entry:
            entry.importance = min(1.0, entry.importance + delta)
            return True
        return False
    
    def weaken(self, entry_id: str, delta: float = 0.1) -> bool:
        """Weaken a memory's importance."""
        entry = self._id_index.get(entry_id)
        if entry:
            entry.importance = max(0.0, entry.importance - delta)
            return True
        return False
    
    def apply_temporal_decay(self) -> int:
        """Apply temporal decay to all memories. Returns count affected."""
        affected = 0
        
        for mt in MemoryType:
            for entry in self._stores.get(mt, []):
                age_hours = (datetime.datetime.now() - entry.timestamp).total_seconds() / 3600.0
                decay = self._decay_rate * age_hours * entry.decay_rate
                
                if decay > 0.001:
                    entry.importance = max(0.0, entry.importance - decay)
                    affected += 1
        
        return affected
    
    def consolidate(
        self,
        importance_threshold: float = 0.7,
    ) -> list[MemoryEntry]:
        """
        Consolidate important episodic memories into semantic memory.
        
        Returns list of consolidated entries.
        """
        consolidated = []
        
        # Find important episodic memories
        episodic = self._stores.get(MemoryType.EPISODIC, [])
        
        for entry in episodic:
            if entry.importance >= importance_threshold:
                # Create semantic memory
                semantic = MemoryEntry(
                    memory_type=MemoryType.SEMANTIC,
                    content=entry.content,
                    importance=entry.importance,
                    confidence=entry.confidence,
                    source_experience_id=entry.id,
                )
                
                self.store(semantic)
                consolidated.append(semantic)
        
        return consolidated
    
    def forget(
        self,
        max_age_days: int = 30,
        importance_threshold: float = 0.2,
    ) -> int:
        """Forget old, unimportant memories. Returns count forgotten."""
        cutoff = datetime.datetime.now() - datetime.timedelta(days=max_age_days)
        forgotten = 0
        
        for mt in MemoryType:
            store = self._stores.get(mt, [])
            to_remove = []
            
            for entry in store:
                if entry.timestamp < cutoff and entry.importance < importance_threshold:
                    to_remove.append(entry)
            
            for entry in to_remove:
                store.remove(entry)
                if entry.id in self._id_index:
                    del self._id_index[entry.id]
                forgotten += 1
        
        self._total_forgotten += forgotten
        return forgotten
    
    def count(self, memory_type: Optional[MemoryType] = None) -> int:
        """Count memories."""
        if memory_type:
            return len(self._stores.get(memory_type, []))
        return self._total_entries()
    
    def get_by_type(self, memory_type: MemoryType) -> list[MemoryEntry]:
        """Get all memories of a type."""
        return self._stores.get(memory_type, []).copy()
    
    def get_statistics(self) -> dict[str, Any]:
        """Get memory statistics."""
        return {
            "total_stored": self._total_stored,
            "total_forgotten": self._total_forgotten,
            "current_count": self._total_entries(),
            "by_type": {
                mt.value: len(self._stores.get(mt, []))
                for mt in MemoryType
            },
        }
    
    def _total_entries(self) -> int:
        """Get total number of entries across all stores."""
        return sum(len(store) for store in self._stores.values())
    
    def _forget_least_important(self) -> None:
        """Remove the least important memories when over capacity."""
        # Find all entries
        all_entries = []
        for mt in MemoryType:
            for entry in self._stores.get(mt, []):
                all_entries.append((entry.importance, entry))
        
        # Sort by importance
        all_entries.sort(key=lambda x: x[0])
        
        # Remove bottom 10%
        remove_count = max(1, len(all_entries) // 10)
        
        for _, entry in all_entries[:remove_count]:
            self._stores[entry.memory_type].remove(entry)
            if entry.id in self._id_index:
                del self._id_index[entry.id]
            self._total_forgotten += 1
    
    def _entry_to_text(self, entry: MemoryEntry) -> str:
        """Convert entry content to text for similarity search."""
        if isinstance(entry.content, dict):
            return " ".join(str(v) for v in entry.content.values())
        elif isinstance(entry.content, str):
            return entry.content
        else:
            return str(entry.content)
    
    def _recency_weight(self, entry: MemoryEntry) -> float:
        """Calculate recency weight (newer = higher weight)."""
        age_hours = (datetime.datetime.now() - entry.timestamp).total_seconds() / 3600.0
        return math.exp(-0.01 * age_hours)  # ~10 hour half-life
