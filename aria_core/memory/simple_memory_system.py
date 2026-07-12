# aria_core/memory/simple_memory_system.py
"""
Reference implementation: a pure‑Python, in‑memory memory system.

It is deliberately simple but complete enough to be used in prototypes
and unit tests.  Real back‑ends (SQLite, Qdrant, FAISS, Redis, Neo4j…) can
replace this class while keeping the same protocol.
"""

from __future__ import annotations

import datetime
import math
from typing import List, Tuple, Dict, Any, Optional

from .interfaces import MemorySystemProtocol
from .models import (
    MemoryItem,
    WorkingMemoryItem,
    EpisodicItem,
    SemanticItem,
    Outcome,
)


def _extract_text(obj: Any) -> str:
    """Extract meaningful text from structured objects for indexing and relevance.

    Handles StructuredInput-like objects, ARIDecision-like objects, dicts,
    and common containers, falling back to str() when nothing useful is found.
    """
    if obj is None:
        return ""
    parts: List[str] = []
    _extract_text_into(obj, parts)
    return " ".join(parts)


def _extract_text_into(obj: Any, parts: List[str]) -> None:
    """Recursively collect text fragments into *parts*."""
    if obj is None:
        return
    # StructuredInput-like: pull out semantic fields
    if hasattr(obj, "raw_text") or hasattr(obj, "intent"):
        _maybe_append(parts, getattr(obj, "raw_text", None))
        _maybe_append(parts, getattr(obj, "intent", None))
        _maybe_append(parts, getattr(obj, "emotional_cue", None))
        for item in getattr(obj, "facts", []) or []:
            _maybe_append(parts, item)
        for item in getattr(obj, "questions", []) or []:
            _maybe_append(parts, item)
        for ent in getattr(obj, "entities", []) or []:
            _maybe_append(parts, getattr(ent, "text", None))
            _maybe_append(parts, getattr(ent, "label", None))
        return
    # ARIDecision-like
    if hasattr(obj, "action_type") and hasattr(obj, "payload"):
        _maybe_append(parts, getattr(obj, "action_type", None))
        payload = getattr(obj, "payload", None)
        if payload is not None:
            _extract_text_into(payload, parts)
        return
    # dict
    if isinstance(obj, dict):
        for v in obj.values():
            _extract_text_into(v, parts)
        return
    # list / tuple / set
    if isinstance(obj, (list, tuple, set)):
        for v in obj:
            _extract_text_into(v, parts)
        return
    # Anything else: convert to string
    _maybe_append(parts, str(obj))


def _maybe_append(parts: List[str], val: Any) -> None:
    if val is not None:
        s = str(val).strip()
        if s:
            parts.append(s)

# ----------------------------------------------------------------------
# Tiny helper for cosine similarity – we avoid heavy deps.
# In a production swap you would plug in a proper vector store.
# ----------------------------------------------------------------------
def _cosine_sim(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _tfidf_vector(text: str, vocab: Dict[str, int]) -> List[float]:
    """Very lightweight TF‑IDF vector (term frequency only for demo)."""
    vec = [0.0] * len(vocab)
    for w in text.lower().split():
        if w in vocab:
            vec[vocab[w]] += 1.0
    # L2 normalise
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class SimpleMemorySystem(MemorySystemProtocol):
    """
    In‑memory stores with basic importance scoring and relevance search.
    Not intended for massive scale – swap with a proper backend when needed.
    """

    def __init__(
        self,
        *,
        working_capacity: int = 20,
        importance_decay_per_day: float = 0.1,
        salience_weight: float = 0.3,
        novelty_weight: float = 0.2,
        recency_weight: float = 0.4,
    ):
        self._working: List[WorkingMemoryItem] = []
        self._working_capacity = working_capacity

        self._episodic: List[EpisodicItem] = []
        self._semantic: List[SemanticItem] = []

        # Simple term‑frequency vocab for the toy TF‑IDF relevance
        self._vocab: Dict[str, int] = {}
        self._next_vocab_id = 0

        # Importance‑tuning parameters
        self._importance_decay_per_day = importance_decay_per_day
        self._salience_weight = salience_weight
        self._novelty_weight = novelty_weight
        self._recency_weight = recency_weight

        # Frequency counter for novelty calculation
        self._term_freq: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Working memory
    # ------------------------------------------------------------------
    def store_working(self, item: WorkingMemoryItem) -> None:
        self._working.append(item)
        self._update_vocab_from_item(item)
        if len(self._working) > self._working_capacity:
            self._working.pop(0)  # FIFO eviction

    def get_working(self, limit: int = 10) -> List[WorkingMemoryItem]:
        return list(reversed(self._working[-limit:]))

    # ------------------------------------------------------------------
    # Episodic memory
    # ------------------------------------------------------------------
    def store_episodic(self, item: EpisodicItem) -> None:
        self._episodic.append(item)
        self._update_vocab_from_item(item)

    def get_episodic(
        self,
        start: Optional[datetime.datetime] = None,
        end: Optional[datetime.datetime] = None,
        limit: int = 100,
    ) -> List[EpisodicItem]:
        filtered = self._episodic
        if start:
            filtered = [e for e in filtered if e.timestamp >= start]
        if end:
            filtered = [e for e in filtered if e.timestamp <= end]
        # most recent first
        filtered = list(reversed(filtered))
        return filtered[:limit]

    # ------------------------------------------------------------------
    # Semantic memory
    # ------------------------------------------------------------------
    def store_semantic(self, item: SemanticItem) -> None:
        self._semantic.append(item)
        self._update_vocab_from_item(item)

    def get_semantic(
        self,
        *,
        query: Optional[str] = None,
        limit: int = 50,
    ) -> List[SemanticItem]:
        if query is None:
            # return most recent first
            return list(reversed(self._semantic))[:limit]
        # simple relevance: TF‑IDF cosine
        q_vec = _tfidf_vector(query, self._vocab)
        scored: List[Tuple[SemanticItem, float]] = []
        for mem in self._semantic:
            f_vec = _tfidf_vector(_extract_text(mem.fact), self._vocab)
            score = _cosine_sim(q_vec, f_vec)
            scored.append((mem, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [mem for mem, s in scored[:limit] if s > 0]

    # ------------------------------------------------------------------
    # Relevance‑based retrieval (combined)
    # ------------------------------------------------------------------
    def retrieve_relevant(
        self,
        cue: str,
        *,
        working_weight: float = 0.4,
        episodic_weight: float = 0.4,
        semantic_weight: float = 0.2,
        limit: int = 10,
    ) -> List[Tuple[MemoryItem, float]]:
        cue_vec = _tfidf_vector(cue, self._vocab)
        results: List[Tuple[MemoryItem, float]] = []

        # Working
        for wm in self._working:
            wm_vec = _tfidf_vector(_extract_text(wm.structured_input), self._vocab)
            sim = _cosine_sim(cue_vec, wm_vec)
            results.append((wm, sim * working_weight))

        # Episodic
        for em in self._episodic:
            em_vec = _tfidf_vector(_extract_text(em.structured_input), self._vocab)
            sim = _cosine_sim(cue_vec, em_vec)
            results.append((em, sim * episodic_weight))

        # Semantic
        for sm in self._semantic:
            sm_vec = _tfidf_vector(_extract_text(sm.fact), self._vocab)
            sim = _cosine_sim(cue_vec, sm_vec)
            results.append((sm, sim * semantic_weight))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    # ------------------------------------------------------------------
    # Importance helpers
    # ------------------------------------------------------------------
    def _compute_base_importance(self, item: MemoryItem) -> float:
        """
        Very simple importance estimator:
          * base 0.5
          * + salience (if emotional cue present)
          * + novelty (inverse document frequency)
          * + recency (exponential decay)
        """
        base = 0.5
        salience = 0.0
        novelty = 0.0
        recency = 0.0

        # salience: look for emotional cue in structured_input or notes
        text_parts: List[str] = []
        if hasattr(item, "structured_input") and item.structured_input:
            text_parts.append(_extract_text(item.structured_input))
        if hasattr(item, "notes") and item.notes:
            text_parts.append(item.notes)

        combined_text = " ".join(text_parts).lower()
        if any(word in combined_text for word in ["happy", "sad", "angry", "excited", "frustrated"]):
            salience = self._salience_weight

        # novelty: inverse document frequency of tokens
        tokens = set(combined_text.split())
        if tokens:
            idf_sum = 0.0
            for t in tokens:
                df = self._term_freq.get(t, 0) + 1  # +1 smoothing
                idf_sum += math.log((1 + len(self._term_freq)) / df)
            novelty = self._novelty_weight * (idf_sum / len(tokens))

        # recency: exponential decay (hours)
        age_hours = (datetime.datetime.now() - item.timestamp).total_seconds() / 3600.0
        recency = self._recency_weight * math.exp(-0.1 * age_hours)  # tune factor 0.1 ≈ 10h half‑life

        imp = base + salience + novelty + recency
        return max(0.0, min(1.0, imp))

    def _update_vocab_from_item(self, item: MemoryItem) -> None:
        """Update the term‑frequency tables used for novelty/TF‑IDF."""
        blob_parts: List[str] = []
        if hasattr(item, "structured_input") and item.structured_input:
            blob_parts.append(_extract_text(item.structured_input))
        if hasattr(item, "fact") and item.fact:
            blob_parts.append(_extract_text(item.fact))
        if hasattr(item, "notes") and item.notes:
            blob_parts.append(item.notes)
        if hasattr(item, "decision") and item.decision:
            blob_parts.append(_extract_text(item.decision))

        blob = " ".join(blob_parts).lower()
        for token in set(blob.split()):
            if token not in self._vocab:
                self._vocab[token] = self._next_vocab_id
                self._next_vocab_id += 1
            self._term_freq[token] = self._term_freq.get(token, 0) + 1

    # ------------------------------------------------------------------
    # Importance update (reinforcement)
    # ------------------------------------------------------------------
    def update_importance(self, item_id: str, delta: float) -> None:
        """Add *delta* to the importance of the item with matching id."""
        for store in (self._working, self._episodic, self._semantic):
            for itm in store:
                if itm.id == item_id:
                    # rebuild with new importance (immutable)
                    new_item = itm.with_importance(itm.importance + delta)
                    idx = store.index(itm)
                    store[idx] = new_item
                    return

    # ------------------------------------------------------------------
    # Consolidation: promote high‑importance working/episodic → semantic
    # ------------------------------------------------------------------
    def consolidate(
        self,
        *,
        importance_threshold: float = 0.7,
        max_age: datetime.timedelta = datetime.timedelta(days=1),
    ) -> int:
        now = datetime.datetime.now()
        promoted = 0

        # Working → Semantic
        new_working: List[WorkingMemoryItem] = []
        for wm in self._working:
            age_ok = (now - wm.timestamp) <= max_age
            if wm.importance >= importance_threshold and age_ok:
                # create a semantic fact – very naive: just store the structured_input as fact
                sem = SemanticItem(
                    importance=wm.importance,
                    fact=wm.structured_input,
                    confidence=wm.importance,
                    metadata={"source": "working", "source_id": wm.id},
                )
                self.store_semantic(sem)
                promoted += 1
            else:
                new_working.append(wm)
        self._working = new_working

        # Episodic → Semantic
        new_episodic: List[EpisodicItem] = []
        for em in self._episodic:
            age_ok = (now - em.timestamp) <= max_age
            if em.importance >= importance_threshold and age_ok:
                sem = SemanticItem(
                    importance=em.importance,
                    fact={
                        "structured_input": em.structured_input,
                        "decision": em.decision,
                        "outcome": em.outcome,
                    },
                    confidence=em.importance,
                    metadata={"source": "episodic", "source_id": em.id},
                )
                self.store_semantic(sem)
                promoted += 1
            else:
                new_episodic.append(em)
        self._episodic = new_episodic

        return promoted

    # ------------------------------------------------------------------
    # Forgetting: drop low‑importance old items
    # ------------------------------------------------------------------
    def forget_low_importance(
        self,
        *,
        threshold: float = 0.2,
        older_than: datetime.timedelta = datetime.timedelta(days=30),
    ) -> int:
        cutoff = datetime.datetime.now() - older_than
        removed = 0

        # Working
        before = len(self._working)
        self._working = [wm for wm in self._working if not (wm.importance < threshold and wm.timestamp < cutoff)]
        removed += before - len(self._working)

        # Episodic
        before = len(self._episodic)
        self._episodic = [em for em in self._episodic if not (em.importance < threshold and em.timestamp < cutoff)]
        removed += before - len(self._episodic)

        # Semantic (we keep semantic longer, but still apply)
        before = len(self._semantic)
        self._semantic = [sm for sm in self._semantic if not (sm.importance < threshold and sm.timestamp < cutoff)]
        removed += before - len(self._semantic)

        return removed

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------
    def size(self) -> Dict[str, int]:
        return {
            "working": len(self._working),
            "episodic": len(self._episodic),
            "semantic": len(self._semantic),
            "vocab_terms": len(self._vocab),
        }

    # ------------------------------------------------------------------
    # Outcome writeback (M2 contract) — out of scope for the in-memory
    # reference implementation. Per the contract: "implementations that
    # don't support writeback must raise NotImplementedError until M2
    # lands." This backend is intentionally not the persistent one;
    # SQLiteMemorySystem implements the full M2 contract.
    # ------------------------------------------------------------------
    def record_outcome(
        self,
        episode_id: str,
        outcome: Outcome,
        *,
        notes: Optional[str] = None,
    ) -> None:
        deltas = {
            Outcome.SUCCESS: 0.10,
            Outcome.PARTIAL: 0.0,
            Outcome.FAILED: -0.05,
            Outcome.IGNORED: -0.05,
            Outcome.CORRECTED: 0.05,
        }
        delta = deltas[outcome]
        for idx, item in enumerate(self._episodic):
            if item.id != episode_id:
                continue
            self._episodic[idx] = EpisodicItem(
                id=item.id,
                timestamp=item.timestamp,
                importance=max(0.0, min(1.0, item.importance + delta)),
                metadata=dict(item.metadata),
                structured_input=item.structured_input,
                decision=item.decision,
                outcome=outcome.value,
                notes=item.notes if notes is None else notes,
            )
            return
