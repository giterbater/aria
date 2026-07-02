from __future__ import annotations

import datetime
import json
import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List


class KnowledgeType(str, Enum):
    FACT = "fact"
    PATTERN = "pattern"
    FAILURE_MODE = "failure_mode"
    SUCCESS_STRATEGY = "success_strategy"
    WORKFLOW = "workflow"
    PREFERENCE = "preference"


@dataclass
class KnowledgeEntry:
    """A single piece of learned knowledge."""
    id: str = field(default_factory=lambda: str(__import__('uuid').uuid4()))
    knowledge_type: KnowledgeType = KnowledgeType.FACT
    key: str = ""
    value: str = ""
    confidence: float = 1.0
    source: str = ""
    tags: list[str] = field(default_factory=list)
    use_count: int = 0
    last_used: datetime.datetime | None = None
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    updated_at: datetime.datetime = field(default_factory=datetime.datetime.now)


class KnowledgeBase:
    """Persistent knowledge store for learned facts, patterns, and strategies.

    Survives restarts. Provides semantic query for relevant knowledge.
    Tracks usage to reinforce valuable knowledge.
    """

    def __init__(self, db_path: str | Path = ":memory:"):
        self._db_path = str(db_path)
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.initialize()

    def initialize(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS knowledge (
                    id TEXT PRIMARY KEY,
                    knowledge_type TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    source TEXT DEFAULT '',
                    tags TEXT DEFAULT '[]',
                    use_count INTEGER DEFAULT 0,
                    last_used TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_knowledge_type
                    ON knowledge(knowledge_type);
                CREATE INDEX IF NOT EXISTS idx_knowledge_key
                    ON knowledge(key);
                """
            )

    def store(self, entry: KnowledgeEntry) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO knowledge
                    (id, knowledge_type, key, value, confidence, source,
                     tags, use_count, last_used, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id, entry.knowledge_type.value, entry.key,
                    entry.value, entry.confidence, entry.source,
                    json.dumps(entry.tags), entry.use_count,
                    entry.last_used.isoformat() if entry.last_used else None,
                    entry.created_at.isoformat(),
                    entry.updated_at.isoformat(),
                ),
            )

    def get(self, key: str) -> KnowledgeEntry | None:
        row = self._conn.execute(
            "SELECT * FROM knowledge WHERE key=?", (key,)
        ).fetchone()
        return self._row_to_entry(row) if row else None

    def get_by_type(self, ktype: KnowledgeType, limit: int = 50) -> List[KnowledgeEntry]:
        rows = self._conn.execute(
            "SELECT * FROM knowledge WHERE knowledge_type=? "
            "ORDER BY confidence DESC, use_count DESC LIMIT ?",
            (ktype.value, limit),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def search(self, query: str, limit: int = 20) -> List[KnowledgeEntry]:
        """Search knowledge by key, value, and tags (token-based)."""
        tokens = query.lower().split()
        if not tokens:
            return []

        conditions = []
        params = []
        for token in tokens:
            q = f"%{token}%"
            conditions.append("(LOWER(key) LIKE ? OR LOWER(value) LIKE ? OR LOWER(tags) LIKE ?)")
            params.extend([q, q, q])

        where = " OR ".join(conditions)
        params.append(limit)
        rows = self._conn.execute(
            f"SELECT * FROM knowledge WHERE {where} "
            "ORDER BY confidence DESC, use_count DESC LIMIT ?",
            params,
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def get_by_tags(self, tags: List[str], limit: int = 20) -> List[KnowledgeEntry]:
        tag_set = set(tags)
        rows = self._conn.execute(
            "SELECT * FROM knowledge ORDER BY confidence DESC LIMIT ?",
            (1000,),
        ).fetchall()
        entries = [
            self._row_to_entry(r) for r in rows
            if tag_set & set(json.loads(r["tags"]))
        ]
        return entries[:limit]

    def record_use(self, entry_id: str) -> None:
        now = datetime.datetime.now().isoformat()
        with self._conn:
            self._conn.execute(
                "UPDATE knowledge SET use_count=use_count+1, last_used=?, updated_at=? "
                "WHERE id=?",
                (now, now, entry_id),
            )

    def reinforce(self, entry_id: str, delta: float = 0.1) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE knowledge SET confidence=MIN(1.0, MAX(0.0, confidence+?)), "
                "updated_at=? WHERE id=?",
                (delta, datetime.datetime.now().isoformat(), entry_id),
            )

    def weaken(self, entry_id: str, delta: float = 0.1) -> None:
        self.reinforce(entry_id, -delta)

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM knowledge").fetchone()
        return row[0] if row else 0

    def count_by_type(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT knowledge_type, COUNT(*) FROM knowledge GROUP BY knowledge_type"
        ).fetchall()
        return {r["knowledge_type"]: r[1] for r in rows}

    def delete(self, entry_id: str) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM knowledge WHERE id=?", (entry_id,))

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.ProgrammingError:
            pass

    def _row_to_entry(self, row: sqlite3.Row) -> KnowledgeEntry:
        return KnowledgeEntry(
            id=row["id"],
            knowledge_type=KnowledgeType(row["knowledge_type"]),
            key=row["key"],
            value=row["value"],
            confidence=row["confidence"],
            source=row["source"],
            tags=json.loads(row["tags"]),
            use_count=row["use_count"],
            last_used=datetime.datetime.fromisoformat(row["last_used"]) if row["last_used"] else None,
            created_at=datetime.datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.datetime.fromisoformat(row["updated_at"]),
        )
