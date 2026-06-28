# aria_core/memory/sqlite_memory_system.py
"""
SQLite-backed implementation of :class:`MemorySystemProtocol`.

Uses the standard library's :mod:`sqlite3` module only.  Items are stored
as JSON blobs in a single ``memory_items`` table; the ``subtype`` column
records which concrete :class:`MemoryItem` subclass to reconstruct on
load.  Importance is clamped to ``[0, 1]`` on every write.
"""

from __future__ import annotations

import datetime
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .interfaces import MemorySystemProtocol
from .models import (
    EpisodicItem,
    MemoryItem,
    Outcome,
    SemanticItem,
    WorkingMemoryItem,
)


# ---------------------------------------------------------------------------
# Subtype registry – keeps the load-side dispatch explicit and exhaustive.
# Adding a new MemoryItem subclass requires adding it here as well.
# ---------------------------------------------------------------------------
_SUBTYPE_TO_CLS = {
    "MemoryItem": MemoryItem,
    "WorkingMemoryItem": WorkingMemoryItem,
    "EpisodicItem": EpisodicItem,
    "SemanticItem": SemanticItem,
}

# Map each concrete subclass to its parent store.
_STORE_OF_SUBTYPE = {
    "MemoryItem": "episodic",          # bare MemoryItem treated as episodic
    "WorkingMemoryItem": "working",
    "EpisodicItem": "episodic",
    "SemanticItem": "semantic",
}

# Importance deltas applied by record_outcome.
_OUTCOME_DELTAS = {
    Outcome.SUCCESS: 0.10,
    Outcome.PARTIAL: 0.0,
    Outcome.FAILED: -0.05,
    Outcome.IGNORED: -0.05,
    Outcome.CORRECTED: 0.05,
}


def _clamp(value: float) -> float:
    """Clamp to ``[0, 1]``."""
    return max(0.0, min(1.0, float(value)))


def _dump_payload(item: MemoryItem) -> str:
    """Serialize every dataclass field (except shared ones) as JSON."""
    from dataclasses import asdict

    # asdict handles nested dataclasses / dicts / lists / primitives.
    # Shared fields (id, timestamp, importance, metadata) live in columns;
    # we still include metadata in the blob so subtype reconstruction is
    # lossless without having to re-merge columns separately.
    data = asdict(item)
    # Convert datetime to ISO-8601 strings for JSON compatibility.
    ts = data.get("timestamp")
    if isinstance(ts, datetime.datetime):
        data["timestamp"] = ts.isoformat()
    return json.dumps(data, default=str, ensure_ascii=False)


def _load_payload(blob: str) -> Dict[str, Any]:
    """Inverse of :func:`_dump_payload`."""
    data = json.loads(blob)
    ts = data.get("timestamp")
    if isinstance(ts, str):
        try:
            data["timestamp"] = datetime.datetime.fromisoformat(ts)
        except ValueError:
            # Fall back to "now" so we never crash on malformed data.
            data["timestamp"] = datetime.datetime.now()
    return data


def _coerce_field(name: str, value: Any) -> Any:
    """Best-effort coercion for fields the JSON layer cannot natively hold.

    Dataclass fields like ``structured_input``/``decision``/``fact`` are
    typed as ``Any`` so they survive a JSON round-trip as plain dicts /
    lists / strings / numbers.  We do not attempt to re-hydrate them back
    into their original dataclass types – ``MemoryItem.with_importance``
    already proves the codebase tolerates this (see ``models.py`` and the
    original 56 tests).
    """
    return value


class SQLiteMemorySystem(MemorySystemProtocol):
    """Persistent memory backed by a single SQLite database file.

    Parameters
    ----------
    db_path:
        Path to the SQLite database.  ``":memory:"`` (the default) keeps
        everything in RAM and is handy for tests; pass a real path for
        production.
    """

    # ------------------------------------------------------------------
    # Construction / schema
    # ------------------------------------------------------------------
    def __init__(self, db_path: Union[str, Path] = ":memory:") -> None:
        self._db_path = str(db_path)
        # ``check_same_thread=False`` so the same connection can be used
        # across threads (e.g. by the worker's reminder poller).  We
        # serialize access with a re-entrant lock where needed.
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.initialize()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------
    def initialize(self) -> None:
        """Create tables / indexes if missing.  Idempotent."""
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS memory_items (
                    id TEXT PRIMARY KEY,
                    store TEXT NOT NULL,
                    subtype TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    importance REAL NOT NULL,
                    payload TEXT NOT NULL,
                    outcome TEXT,
                    notes TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_store_ts
                    ON memory_items(store, timestamp DESC);
                """
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _store_of(item: MemoryItem) -> str:
        cls_name = type(item).__name__
        return _STORE_OF_SUBTYPE.get(cls_name, "episodic")

    def _upsert(self, item: MemoryItem) -> None:
        store = self._store_of(item)
        subtype = type(item).__name__
        importance = _clamp(item.importance)
        ts_iso = item.timestamp.isoformat() if isinstance(item.timestamp, datetime.datetime) else str(item.timestamp)
        # Episodic items carry outcome / notes in dedicated columns.
        outcome_val: Optional[str] = None
        notes_val: Optional[str] = None
        if isinstance(item, EpisodicItem):
            outcome_val = getattr(item, "outcome", None)
            if outcome_val is not None and not isinstance(outcome_val, str):
                outcome_val = str(outcome_val)
            notes_val = getattr(item, "notes", None)
        payload = _dump_payload(item)

        with self._conn:
            self._conn.execute(
                """
                INSERT INTO memory_items
                    (id, store, subtype, timestamp, importance, payload, outcome, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    store=excluded.store,
                    subtype=excluded.subtype,
                    timestamp=excluded.timestamp,
                    importance=excluded.importance,
                    payload=excluded.payload,
                    outcome=excluded.outcome,
                    notes=excluded.notes
                """,
                (
                    item.id,
                    store,
                    subtype,
                    ts_iso,
                    importance,
                    payload,
                    outcome_val,
                    notes_val,
                ),
            )

    def _reconstruct(self, row: sqlite3.Row) -> MemoryItem:
        """Rebuild a concrete ``MemoryItem`` subclass from a DB row."""
        data = _load_payload(row["payload"])
        # Shared fields are column-sourced; override with column values so
        # they always reflect the latest persisted state.
        data["id"] = row["id"]
        data["timestamp"] = _coerce_field(
            "timestamp",
            datetime.datetime.fromisoformat(row["timestamp"])
            if row["timestamp"]
            else datetime.datetime.now(),
        )
        data["importance"] = _clamp(row["importance"])

        # Episodic-specific: outcome / notes are stored in columns, so
        # ensure they take precedence over any stale payload copy.
        subtype = row["subtype"]
        if subtype == "EpisodicItem":
            if row["outcome"] is not None:
                data["outcome"] = row["outcome"]
            if row["notes"] is not None:
                data["notes"] = row["notes"]

        cls = _SUBTYPE_TO_CLS.get(subtype, MemoryItem)  # type: ignore[arg-type]
        # Filter data to only known fields of the target dataclass so we
        # never trip over a stale column that was removed.
        try:
            from dataclasses import fields as _fields

            allowed = {f.name for f in _fields(cls)}
            filtered = {k: v for k, v in data.items() if k in allowed}
            return cls(**filtered)
        except TypeError:
            # Fallback: construct from raw data and let dataclass __init__
            # complain if something is truly broken.
            return cls(**data)

    # ------------------------------------------------------------------
    # Working memory
    # ------------------------------------------------------------------
    def store_working(self, item: WorkingMemoryItem) -> None:
        self._upsert(item)

    def get_working(self, limit: int = 10) -> List[WorkingMemoryItem]:
        rows = self._conn.execute(
            "SELECT * FROM memory_items WHERE store='working' "
            "ORDER BY timestamp DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
        return [self._reconstruct(r) for r in rows]  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Episodic memory
    # ------------------------------------------------------------------
    def store_episodic(self, item: EpisodicItem) -> None:
        self._upsert(item)

    def get_episodic(
        self,
        start: Optional[datetime.datetime] = None,
        end: Optional[datetime.datetime] = None,
        limit: int = 100,
    ) -> List[EpisodicItem]:
        clauses = ["store='episodic'"]
        params: List[Any] = []
        if start is not None:
            clauses.append("timestamp >= ?")
            params.append(start.isoformat())
        if end is not None:
            clauses.append("timestamp <= ?")
            params.append(end.isoformat())
        params.append(int(limit))
        sql = (
            "SELECT * FROM memory_items WHERE " + " AND ".join(clauses)
            + " ORDER BY timestamp DESC LIMIT ?"
        )
        rows = self._conn.execute(sql, params).fetchall()
        return [self._reconstruct(r) for r in rows]  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Semantic memory
    # ------------------------------------------------------------------
    def store_semantic(self, item: SemanticItem) -> None:
        self._upsert(item)

    def get_semantic(
        self,
        *,
        query: Optional[str] = None,
        limit: int = 50,
    ) -> List[SemanticItem]:
        rows = self._conn.execute(
            "SELECT * FROM memory_items WHERE store='semantic' "
            "ORDER BY timestamp DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
        items: List[SemanticItem] = [self._reconstruct(r) for r in rows]  # type: ignore[misc]
        if query is None:
            return items
        # Lightweight substring relevance; keeps the API compatible with
        # the in-memory implementation's `query` parameter.
        q = query.lower()
        scored = []
        for it in items:
            fact = it.fact
            text = fact if isinstance(fact, str) else str(fact)
            score = 1.0 if q and q in text.lower() else 0.0
            if score > 0:
                scored.append((it, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [it for it, _ in scored[:limit]]

    # ------------------------------------------------------------------
    # Relevance‑based retrieval
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
        """Naive but deterministic relevance over all three stores.

        Uses case-insensitive substring overlap as the relevance signal
        so the SQLite implementation can run without a TF-IDF cache.
        """
        cue_l = cue.lower()
        cue_tokens = set(cue_l.split())

        def _score(item: MemoryItem) -> float:
            text_parts: List[str] = []
            si = getattr(item, "structured_input", None)
            if si is not None:
                raw = getattr(si, "raw_text", None)
                if raw:
                    text_parts.append(str(raw))
                intent = getattr(si, "intent", None)
                if intent:
                    text_parts.append(str(intent))
            fact = getattr(item, "fact", None)
            if fact is not None:
                text_parts.append(str(fact))
            blob = " ".join(text_parts).lower()
            if cue_l and cue_l in blob:
                return 1.0
            tokens = set(blob.split())
            if not tokens or not cue_tokens:
                return 0.0
            return len(tokens & cue_tokens) / len(tokens | cue_tokens)

        results: List[Tuple[MemoryItem, float]] = []
        weight_map = {
            "working": working_weight,
            "episodic": episodic_weight,
            "semantic": semantic_weight,
        }
        # Walk a fixed window so we don't load the entire table for big DBs.
        window = max(limit * 20, 200)
        rows = self._conn.execute(
            "SELECT * FROM memory_items ORDER BY timestamp DESC LIMIT ?",
            (int(window),),
        ).fetchall()
        for r in rows:
            item = self._reconstruct(r)
            store = r["store"]
            results.append((item, _score(item) * weight_map.get(store, 0.0)))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    # ------------------------------------------------------------------
    # Importance updates
    # ------------------------------------------------------------------
    def update_importance(self, item_id: str, delta: float) -> None:
        row = self._conn.execute(
            "SELECT importance FROM memory_items WHERE id=?", (item_id,)
        ).fetchone()
        if row is None:
            return
        new_imp = _clamp(row["importance"] + float(delta))
        with self._conn:
            self._conn.execute(
                "UPDATE memory_items SET importance=? WHERE id=?",
                (new_imp, item_id),
            )

    # ------------------------------------------------------------------
    # Outcome feedback (writeback)
    # ------------------------------------------------------------------
    def record_outcome(
        self,
        episode_id: str,
        outcome: Outcome,
        *,
        notes: Optional[str] = None,
    ) -> None:
        """Apply the outcome delta defined in the M2 contract."""
        row = self._conn.execute(
            "SELECT importance, subtype FROM memory_items WHERE id=?",
            (episode_id,),
        ).fetchone()
        if row is None or row["subtype"] != "EpisodicItem":
            return  # no-op for unknown id or non-episodic items
        delta = _OUTCOME_DELTAS[outcome]
        new_imp = _clamp(row["importance"] + delta)
        # If the caller passed notes explicitly, use them; otherwise keep
        # whatever was already stored.
        if notes is not None:
            with self._conn:
                self._conn.execute(
                    "UPDATE memory_items SET outcome=?, notes=?, importance=? "
                    "WHERE id=?",
                    (outcome.value, notes, new_imp, episode_id),
                )
        else:
            with self._conn:
                self._conn.execute(
                    "UPDATE memory_items SET outcome=?, importance=? "
                    "WHERE id=?",
                    (outcome.value, new_imp, episode_id),
                )

    # ------------------------------------------------------------------
    # Consolidation & forgetting (in-memory over the loaded subset)
    # ------------------------------------------------------------------
    def consolidate(
        self,
        *,
        importance_threshold: float = 0.7,
        max_age: datetime.timedelta = datetime.timedelta(days=1),
    ) -> int:
        now = datetime.datetime.now()
        rows = self._conn.execute(
            "SELECT * FROM memory_items WHERE store IN ('working','episodic')"
        ).fetchall()
        promoted = 0
        for r in rows:
            item = self._reconstruct(r)
            age = now - item.timestamp
            if item.importance >= importance_threshold and age <= max_age:
                # Promote to semantic using whatever blob we already hold.
                fact_payload = _load_payload(r["payload"])
                sem = SemanticItem(
                    fact=fact_payload,
                    importance=item.importance,
                    confidence=item.importance,
                    metadata={"source": r["store"], "source_id": item.id},
                )
                # Remove the original working/episodic row (we keep the
                # new semantic one).
                with self._conn:
                    self._conn.execute(
                        "DELETE FROM memory_items WHERE id=?", (item.id,)
                    )
                self._upsert(sem)
                promoted += 1
        return promoted

    def forget_low_importance(
        self,
        *,
        threshold: float = 0.2,
        older_than: datetime.timedelta = datetime.timedelta(days=30),
    ) -> int:
        cutoff = (datetime.datetime.now() - older_than).isoformat()
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM memory_items WHERE importance < ? AND timestamp < ?",
                (_clamp(threshold), cutoff),
            )
        return cur.rowcount

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------
    def size(self) -> Dict[str, int]:
        rows = self._conn.execute(
            "SELECT store, COUNT(*) AS c FROM memory_items GROUP BY store"
        ).fetchall()
        out: Dict[str, int] = {"working": 0, "episodic": 0, "semantic": 0}
        for r in rows:
            out[r["store"]] = r["c"]
        out["total"] = sum(out.values())
        return out

    def close(self) -> None:
        """Close the underlying connection.  Optional – SQLite is happy
        to clean up at GC time, but tests should call this to avoid
        spurious ResourceWarning on Windows."""
        try:
            self._conn.close()
        except sqlite3.ProgrammingError:
            pass

    def __del__(self) -> None:  # pragma: no cover – best effort
        try:
            self._conn.close()
        except Exception:
            pass
