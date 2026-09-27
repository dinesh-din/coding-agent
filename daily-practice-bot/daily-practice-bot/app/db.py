"""
A one-table SQLite log of every agent run. This is what makes the agent
auditable instead of a black box — the FastAPI /history endpoint just reads
this table.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from app.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    problem_id TEXT,
    problem_title TEXT,
    status TEXT NOT NULL,
    dry_run INTEGER NOT NULL,
    commit_sha TEXT,
    pr_url TEXT,
    detail TEXT
);
"""


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def log_run(
    problem_id: str,
    problem_title: str,
    status: str,
    dry_run: bool,
    commit_sha: str | None,
    pr_url: str | None,
    detail: dict[str, Any],
) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO runs (started_at, problem_id, problem_title, status, "
            "dry_run, commit_sha, pr_url, detail) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                problem_id, problem_title, status, int(dry_run),
                commit_sha, pr_url, json.dumps(detail),
            ),
        )
        return cur.lastrowid


def list_runs(limit: int = 30) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]


def get_run(run_id: int) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None
