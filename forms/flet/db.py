"""SQLite layer (raw SQL, stdlib sqlite3). Mirrors the Flutter app's db.dart
schema exactly: table `contact` (pulled inbox rows) and `settings`
(worker_url / pull_token / last_backup_date as key-value pairs).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

_CREATE_CONTACT = """
CREATE TABLE IF NOT EXISTS contact (
  remote_id INTEGER PRIMARY KEY,
  pulled_at TEXT NOT NULL DEFAULT (datetime('now')),
  created_at TEXT NOT NULL,
  email TEXT,
  payload TEXT NOT NULL,
  confirmed INTEGER NOT NULL DEFAULT 0,
  handled INTEGER NOT NULL DEFAULT 0
)
"""

_CREATE_SETTINGS = """
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
)
"""


@dataclass
class Contact:
    remote_id: int
    pulled_at: str
    created_at: str
    email: str | None
    payload: str
    confirmed: bool
    handled: bool

    @staticmethod
    def from_row(row: sqlite3.Row) -> "Contact":
        return Contact(
            remote_id=row["remote_id"],
            pulled_at=row["pulled_at"],
            created_at=row["created_at"],
            email=row["email"],
            payload=row["payload"],
            confirmed=bool(row["confirmed"]),
            handled=bool(row["handled"]),
        )


def open_db(data_dir: Path) -> sqlite3.Connection:
    data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(data_dir / "inbox.db")
    conn.row_factory = sqlite3.Row
    conn.execute(_CREATE_CONTACT)
    conn.execute(_CREATE_SETTINGS)
    conn.commit()
    return conn


def get_setting(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute(
        "SELECT value FROM settings WHERE key = ?", (key,)
    ).fetchone()
    return row["value"] if row else None


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()
