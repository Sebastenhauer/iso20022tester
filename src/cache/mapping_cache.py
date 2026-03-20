"""Semantic Caching für Feld-Mappings (vorbereitet für KI-Integration)."""

import json
import os
import sqlite3
from datetime import datetime
from typing import Optional


class MappingCache:
    """SQLite-basierter Cache für Feld-Mappings."""

    def __init__(self, db_path: str = ".cache/mapping_cache.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mappings (
                    input_key TEXT PRIMARY KEY,
                    xpath TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    source TEXT DEFAULT 'static'
                )
            """)

    def get(self, input_key: str) -> Optional[str]:
        """Sucht ein Mapping im Cache."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT xpath FROM mappings WHERE input_key = ?",
                (input_key,),
            ).fetchone()
            return row[0] if row else None

    def put(self, input_key: str, xpath: str, source: str = "static") -> None:
        """Speichert ein Mapping im Cache."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO mappings (input_key, xpath, created_at, source)
                   VALUES (?, ?, ?, ?)""",
                (input_key, xpath, datetime.now().isoformat(), source),
            )

    def clear(self) -> None:
        """Leert den Cache."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM mappings")
