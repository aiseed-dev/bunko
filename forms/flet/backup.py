"""Daily backup of inbox.db, keeping the last 30 days. Mirrors backup.dart."""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from db import get_setting, set_setting

_KEEP_DAYS = 30


def run_daily_backup_if_needed(conn: sqlite3.Connection, data_dir: Path) -> None:
    today = datetime.now().strftime("%Y%m%d")
    if get_setting(conn, "last_backup_date") == today:
        return

    db_file = data_dir / "inbox.db"
    if not db_file.exists():
        return

    backup_dir = data_dir.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db_file, backup_dir / f"inbox-{today}.db")

    cutoff = datetime.now() - timedelta(days=_KEEP_DAYS)
    for entry in backup_dir.iterdir():
        if entry.is_file() and datetime.fromtimestamp(entry.stat().st_mtime) < cutoff:
            entry.unlink()

    set_setting(conn, "last_backup_date", today)
