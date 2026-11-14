"""SQLite snapshots scoped to an opaque browser session; expire after 24 hours."""

import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connection():
    path = Path(os.getenv("AIRLEDGER_DB", "data/airledger.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=15) as db:
        db.row_factory = sqlite3.Row
        db.execute(
            "CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, owner TEXT NOT NULL, kind TEXT NOT NULL, created REAL NOT NULL, payload TEXT NOT NULL)"
        )
        db.execute("CREATE INDEX IF NOT EXISTS records_owner ON records(owner, kind, created)")
        db.execute("DELETE FROM records WHERE created < ?", (time.time() - 86400,))
        yield db


def save(owner: str, kind: str, payload: dict, record_id: str | None = None) -> str:
    record_id = record_id or uuid.uuid4().hex
    with connection() as db:
        existing = db.execute(
            "SELECT id FROM records WHERE id=? AND owner=? AND kind=?", (record_id, owner, kind)
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE records SET payload=? WHERE id=? AND owner=?",
                (json.dumps(payload, allow_nan=False), record_id, owner),
            )
        else:
            count = db.execute(
                "SELECT COUNT(*) FROM records WHERE owner=? AND kind=?", (owner, kind)
            ).fetchone()[0]
            if count >= (10 if kind == "dataset" else 20):
                raise ValueError("Session storage limit reached. Clear your workspace to continue.")
            db.execute(
                "INSERT INTO records VALUES (?, ?, ?, ?, ?)",
                (record_id, owner, kind, time.time(), json.dumps(payload, allow_nan=False)),
            )
    return record_id


def get(owner: str, kind: str, record_id: str) -> dict | None:
    with connection() as db:
        row = db.execute(
            "SELECT payload FROM records WHERE id=? AND owner=? AND kind=?",
            (record_id, owner, kind),
        ).fetchone()
    return json.loads(row[0]) if row else None


def brief_history(owner: str) -> list[dict]:
    """Project metadata in SQLite; never load every raw snapshot to render an index."""
    with connection() as db:
        rows = db.execute(
            "SELECT id, json_extract(payload, '$.created_at') AS created_at, "
            "json_extract(payload, '$.role') AS role, "
            "json_extract(payload, '$.filename') AS filename, "
            "json_extract(payload, '$.mode') AS mode, "
            "json_extract(payload, '$.language') AS language "
            "FROM records WHERE owner=? AND kind='brief' ORDER BY created DESC",
            (owner,),
        ).fetchall()
    return [dict(row) for row in rows]


def previous_brief(owner: str, role: str) -> dict | None:
    """Read one matching analysis, without deserializing historical source rows."""
    with connection() as db:
        row = db.execute(
            "SELECT id, json_extract(payload, '$.analysis') AS analysis, "
            "json_extract(payload, '$.source_sha256') AS source_sha256 "
            "FROM records WHERE owner=? AND kind='brief' "
            "AND json_extract(payload, '$.role')=? ORDER BY created DESC LIMIT 1",
            (owner, role),
        ).fetchone()
    return (
        {
            "id": row["id"],
            "analysis": json.loads(row["analysis"]),
            "source_sha256": row["source_sha256"],
        }
        if row
        else None
    )


def clear(owner: str):
    with connection() as db:
        db.execute("DELETE FROM records WHERE owner=?", (owner,))
