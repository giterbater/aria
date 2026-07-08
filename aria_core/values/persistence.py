# aria_core/values/persistence.py
"""
SQLite persistence for value formation state.

Stores:
- Values (type, strength, direction, evidence_count, timestamps)
- Value conflicts
- Value coherence history
"""

from __future__ import annotations

import datetime
import json
import sqlite3
from pathlib import Path
from typing import List, Tuple

from .formation import ValueState, ValueType, Value


class ValueStore:
    """SQLite-backed persistence for value formation state."""
    
    def __init__(self, db_path: str | Path = ":memory:"):
        self._db_path = str(db_path)
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._initialize()
    
    def _initialize(self) -> None:
        with self._conn:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS value_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    value_type TEXT NOT NULL UNIQUE,
                    strength REAL NOT NULL,
                    direction TEXT NOT NULL,
                    evidence_count INTEGER NOT NULL,
                    first_observed TEXT NOT NULL,
                    last_reinforced TEXT NOT NULL,
                    is_stable BOOLEAN NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS value_conflicts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    value_a TEXT NOT NULL,
                    value_b TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    detected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    resolved BOOLEAN DEFAULT FALSE
                );
                
                CREATE TABLE IF NOT EXISTS value_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_number INTEGER NOT NULL,
                    coherence REAL NOT NULL,
                    total_signals INTEGER NOT NULL,
                    stable_value_count INTEGER NOT NULL,
                    conflict_count INTEGER NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            """)
    
    def save_value(self, value: Value) -> None:
        """Save or update a value."""
        with self._conn:
            self._conn.execute("""
                INSERT INTO value_entries 
                    (value_type, strength, direction, evidence_count,
                     first_observed, last_reinforced, is_stable)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(value_type) DO UPDATE SET
                    strength = excluded.strength,
                    direction = excluded.direction,
                    evidence_count = excluded.evidence_count,
                    last_reinforced = excluded.last_reinforced,
                    is_stable = excluded.is_stable,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                value.value_type.value,
                value.strength,
                value.direction,
                value.evidence_count,
                value.first_observed.isoformat(),
                value.last_reinforced.isoformat(),
                value.is_stable,
            ))
    
    def load_values(self) -> List[Value]:
        """Load all values."""
        rows = self._conn.execute(
            "SELECT * FROM value_entries ORDER BY strength DESC"
        ).fetchall()
        
        values = []
        for row in rows:
            value = Value(
                value_type=ValueType(row["value_type"]),
                strength=row["strength"],
                direction=row["direction"],
                evidence_count=row["evidence_count"],
                first_observed=datetime.datetime.fromisoformat(row["first_observed"]),
                last_reinforced=datetime.datetime.fromisoformat(row["last_reinforced"]),
            )
            values.append(value)
        
        return values
    
    def save_conflict(
        self,
        value_a: str,
        value_b: str,
        reason: str,
    ) -> None:
        """Record a value conflict."""
        with self._conn:
            self._conn.execute("""
                INSERT INTO value_conflicts (value_a, value_b, reason)
                VALUES (?, ?, ?)
            """, (value_a, value_b, reason))
    
    def load_conflicts(self, include_resolved: bool = False) -> List[dict]:
        """Load value conflicts."""
        query = "SELECT * FROM value_conflicts"
        if not include_resolved:
            query += " WHERE resolved = FALSE"
        query += " ORDER BY detected_at DESC"
        
        rows = self._conn.execute(query).fetchall()
        return [
            {
                "value_a": row["value_a"],
                "value_b": row["value_b"],
                "reason": row["reason"],
                "detected_at": row["detected_at"],
                "resolved": row["resolved"],
            }
            for row in rows
        ]
    
    def save_snapshot(
        self,
        cycle_number: int,
        state: ValueState,
    ) -> None:
        """Save a snapshot of value state at a given cycle."""
        snapshot_data = {
            "values": {
                k: {
                    "type": v.value_type.value,
                    "strength": v.strength,
                    "direction": v.direction,
                    "evidence_count": v.evidence_count,
                    "is_stable": v.is_stable,
                }
                for k, v in state.values.items()
            },
            "conflicts": [
                {"value_a": c[0], "value_b": c[1], "reason": c[2]}
                for c in state.conflicts
            ],
            "total_signals": state.total_signals,
            "value_coherence": state.value_coherence,
        }
        
        with self._conn:
            self._conn.execute("""
                INSERT INTO value_snapshots 
                    (cycle_number, coherence, total_signals, 
                     stable_value_count, conflict_count, snapshot_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                cycle_number,
                state.value_coherence,
                state.total_signals,
                len([v for v in state.values.values() if v.is_stable]),
                len(state.conflicts),
                json.dumps(snapshot_data, default=str),
            ))
    
    def load_snapshots(self, limit: int = 100) -> List[dict]:
        """Load recent snapshots."""
        rows = self._conn.execute("""
            SELECT * FROM value_snapshots 
            ORDER BY cycle_number DESC 
            LIMIT ?
        """, (limit,)).fetchall()
        
        snapshots = []
        for row in rows:
            snapshot = {
                "cycle_number": row["cycle_number"],
                "coherence": row["coherence"],
                "total_signals": row["total_signals"],
                "stable_value_count": row["stable_value_count"],
                "conflict_count": row["conflict_count"],
                "snapshot": json.loads(row["snapshot_json"]),
                "created_at": row["created_at"],
            }
            snapshots.append(snapshot)
        
        return list(reversed(snapshots))
    
    def get_coherence_history(self) -> List[tuple[int, float]]:
        """Get coherence values over time for plotting."""
        rows = self._conn.execute("""
            SELECT cycle_number, coherence 
            FROM value_snapshots 
            ORDER BY cycle_number
        """).fetchall()
        
        return [(row["cycle_number"], row["coherence"]) for row in rows]
    
    def close(self) -> None:
        """Close the database connection."""
        try:
            self._conn.close()
        except sqlite3.ProgrammingError:
            pass
    
    def __del__(self) -> None:
        self.close()
