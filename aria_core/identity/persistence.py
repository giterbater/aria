# aria_core/identity/persistence.py
"""
SQLite persistence for identity formation state.

Stores:
- Preferences (dimension, value, strength, evidence_count, timestamps)
- Stable traits
- Identity coherence history
"""

from __future__ import annotations

import datetime
import json
import sqlite3
from pathlib import Path
from typing import List, Optional

from .formation import IdentityState, IdentityDimension, Preference


class IdentityStore:
    """SQLite-backed persistence for identity formation state."""
    
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
                CREATE TABLE IF NOT EXISTS identity_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dimension TEXT NOT NULL,
                    value TEXT NOT NULL,
                    strength REAL NOT NULL,
                    evidence_count INTEGER NOT NULL,
                    first_observed TEXT NOT NULL,
                    last_reinforced TEXT NOT NULL,
                    is_stable BOOLEAN NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(dimension, value)
                );
                
                CREATE TABLE IF NOT EXISTS identity_traits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trait_name TEXT NOT NULL UNIQUE,
                    trait_value REAL NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS identity_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_number INTEGER NOT NULL,
                    coherence REAL NOT NULL,
                    total_experiences INTEGER NOT NULL,
                    stable_preference_count INTEGER NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            """)
    
    def save_preference(self, preference: Preference) -> None:
        """Save or update a preference."""
        with self._conn:
            self._conn.execute("""
                INSERT INTO identity_preferences 
                    (dimension, value, strength, evidence_count, 
                     first_observed, last_reinforced, is_stable)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(dimension, value) DO UPDATE SET
                    strength = excluded.strength,
                    evidence_count = excluded.evidence_count,
                    last_reinforced = excluded.last_reinforced,
                    is_stable = excluded.is_stable,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                preference.dimension.value,
                preference.value,
                preference.strength,
                preference.evidence_count,
                preference.first_observed.isoformat(),
                preference.last_reinforced.isoformat(),
                preference.is_stable,
            ))
    
    def load_preferences(self) -> List[Preference]:
        """Load all preferences."""
        rows = self._conn.execute(
            "SELECT * FROM identity_preferences ORDER BY strength DESC"
        ).fetchall()
        
        preferences = []
        for row in rows:
            pref = Preference(
                dimension=IdentityDimension(row["dimension"]),
                value=row["value"],
                strength=row["strength"],
                evidence_count=row["evidence_count"],
                first_observed=datetime.datetime.fromisoformat(row["first_observed"]),
                last_reinforced=datetime.datetime.fromisoformat(row["last_reinforced"]),
            )
            preferences.append(pref)
        
        return preferences
    
    def save_trait(self, trait_name: str, trait_value: float) -> None:
        """Save or update a stable trait."""
        with self._conn:
            self._conn.execute("""
                INSERT INTO identity_traits (trait_name, trait_value)
                VALUES (?, ?)
                ON CONFLICT(trait_name) DO UPDATE SET
                    trait_value = excluded.trait_value,
                    updated_at = CURRENT_TIMESTAMP
            """, (trait_name, trait_value))
    
    def load_traits(self) -> dict[str, float]:
        """Load all stable traits."""
        rows = self._conn.execute("SELECT * FROM identity_traits").fetchall()
        return {row["trait_name"]: row["trait_value"] for row in rows}
    
    def save_snapshot(
        self,
        cycle_number: int,
        state: IdentityState,
    ) -> None:
        """Save a snapshot of identity state at a given cycle."""
        snapshot_data = {
            "preferences": {
                k: {
                    "dimension": v.dimension.value,
                    "value": v.value,
                    "strength": v.strength,
                    "evidence_count": v.evidence_count,
                    "is_stable": v.is_stable,
                }
                for k, v in state.preferences.items()
            },
            "stable_traits": state.stable_traits,
            "total_experiences": state.total_experiences,
            "identity_coherence": state.identity_coherence,
        }
        
        with self._conn:
            self._conn.execute("""
                INSERT INTO identity_snapshots 
                    (cycle_number, coherence, total_experiences, 
                     stable_preference_count, snapshot_json)
                VALUES (?, ?, ?, ?, ?)
            """, (
                cycle_number,
                state.identity_coherence,
                state.total_experiences,
                len([p for p in state.preferences.values() if p.is_stable]),
                json.dumps(snapshot_data, default=str),
            ))
    
    def load_snapshots(self, limit: int = 100) -> List[dict]:
        """Load recent snapshots."""
        rows = self._conn.execute("""
            SELECT * FROM identity_snapshots 
            ORDER BY cycle_number DESC 
            LIMIT ?
        """, (limit,)).fetchall()
        
        snapshots = []
        for row in rows:
            snapshot = {
                "cycle_number": row["cycle_number"],
                "coherence": row["coherence"],
                "total_experiences": row["total_experiences"],
                "stable_preference_count": row["stable_preference_count"],
                "snapshot": json.loads(row["snapshot_json"]),
                "created_at": row["created_at"],
            }
            snapshots.append(snapshot)
        
        return list(reversed(snapshots))
    
    def get_coherence_history(self) -> List[tuple[int, float]]:
        """Get coherence values over time for plotting."""
        rows = self._conn.execute("""
            SELECT cycle_number, coherence 
            FROM identity_snapshots 
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
