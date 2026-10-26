from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

class EventStore:
    """SQLite operational event log; API keys and model prompts are not stored."""
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or os.getenv("SIVA_EVENT_DB", "data/events.db")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, agent_name TEXT NOT NULL, task TEXT NOT NULL, event_type TEXT NOT NULL, status TEXT NOT NULL, summary TEXT NOT NULL DEFAULT '', provider TEXT NOT NULL DEFAULT '', model TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id)")
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn
    def add_event(self, run_id: str, agent_name: str, task: str, event_type: str, status: str, summary: str = "", provider: str = "", model: str = "") -> None:
        values = (run_id, agent_name, task[:2000], event_type, status, summary[:4000], provider, model, datetime.now(timezone.utc).isoformat())
        with self._connect() as conn:
            conn.execute("INSERT INTO events (run_id, agent_name, task, event_type, status, summary, provider, model, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", values)
    def recent_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (min(max(int(limit), 1), 1000),)).fetchall()
        return [dict(row) for row in rows]
