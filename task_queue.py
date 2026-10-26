from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PersistentTaskQueue:
    """SQLite-backed leased task queue with retry/recovery semantics.

    Set SIVA_QUEUE_DB to a durable shared-volume path. SQLite on an ephemeral
    Streamlit/GitHub Actions filesystem is not cross-instance persistent.
    """

    def __init__(self, db_path: str | None = None, max_attempts: int = 3) -> None:
        self.db_path = db_path or os.getenv("SIVA_QUEUE_DB", "data/task-queue.db")
        self.max_attempts = max(1, int(max_attempts))
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL,
                    available_at TEXT NOT NULL,
                    lease_until TEXT,
                    worker_id TEXT,
                    last_error TEXT NOT NULL DEFAULT '',
                    result TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_ready ON tasks(status, available_at, created_at)")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=15000")
        return conn

    def enqueue(self, payload: dict[str, Any], task_id: str | None = None) -> str:
        now = _now().isoformat()
        ident = task_id or str(uuid.uuid4())
        encoded = json.dumps(payload, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO tasks(id,payload,status,attempts,max_attempts,available_at,created_at,updated_at) VALUES(?,?,'queued',0,?,?,?,?)",
                (ident, encoded, self.max_attempts, now, now, now),
            )
        return ident

    def claim(self, worker_id: str, lease_seconds: int = 300) -> dict[str, Any] | None:
        now = _now()
        until = (now + timedelta(seconds=max(30, int(lease_seconds)))).isoformat()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            # Requeue expired leases or finalize exhausted tasks after worker crashes.
            conn.execute(
                """UPDATE tasks SET status=CASE WHEN attempts >= max_attempts THEN 'failed' ELSE 'queued' END,
                   worker_id=NULL, lease_until=NULL, updated_at=?
                   WHERE status='running' AND lease_until IS NOT NULL AND lease_until < ?""",
                (now.isoformat(), now.isoformat()),
            )
            row = conn.execute(
                "SELECT * FROM tasks WHERE status='queued' AND available_at <= ? ORDER BY created_at,id LIMIT 1",
                (now.isoformat(),),
            ).fetchone()
            if row is None:
                conn.commit()
                return None
            changed = conn.execute(
                """UPDATE tasks SET status='running', attempts=attempts+1, worker_id=?, lease_until=?, updated_at=?
                   WHERE id=? AND status='queued'""",
                (worker_id, until, now.isoformat(), row["id"]),
            ).rowcount
            if changed != 1:
                conn.rollback()
                return None
            claimed = conn.execute("SELECT * FROM tasks WHERE id=?", (row["id"],)).fetchone()
            conn.commit()
        item = dict(claimed)
        item["payload"] = json.loads(item["payload"])
        return item

    def heartbeat(self, task_id: str, worker_id: str, lease_seconds: int = 300) -> bool:
        now = _now()
        until = (now + timedelta(seconds=max(30, int(lease_seconds)))).isoformat()
        with self._connect() as conn:
            result = conn.execute(
                "UPDATE tasks SET lease_until=?,updated_at=? WHERE id=? AND status='running' AND worker_id=?",
                (until, now.isoformat(), task_id, worker_id),
            )
            return result.rowcount == 1

    def complete(self, task_id: str, worker_id: str, result: dict[str, Any] | str = "") -> bool:
        now = _now().isoformat()
        encoded = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        with self._connect() as conn:
            changed = conn.execute(
                """UPDATE tasks SET status='completed',result=?,worker_id=NULL,lease_until=NULL,updated_at=?
                   WHERE id=? AND status='running' AND worker_id=?""",
                (encoded, now, task_id, worker_id),
            )
            return changed.rowcount == 1

    def fail(self, task_id: str, worker_id: str, error: str, retry_delay_seconds: int = 30) -> str:
        now = _now()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT attempts,max_attempts FROM tasks WHERE id=? AND status='running' AND worker_id=?",
                (task_id, worker_id),
            ).fetchone()
            if row is None:
                return "not_owned"
            retry = int(row["attempts"]) < int(row["max_attempts"])
            status = "queued" if retry else "failed"
            available = (now + timedelta(seconds=max(0, int(retry_delay_seconds)))).isoformat() if retry else now.isoformat()
            conn.execute(
                """UPDATE tasks SET status=?,available_at=?,last_error=?,worker_id=NULL,lease_until=NULL,updated_at=?
                   WHERE id=? AND status='running' AND worker_id=?""",
                (status, available, str(error)[:4000], now.isoformat(), task_id, worker_id),
            )
        return status

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["payload"] = json.loads(item["payload"])
        return item

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (min(max(1, int(limit)), 500),)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item["payload"])
            result.append(item)
        return result
