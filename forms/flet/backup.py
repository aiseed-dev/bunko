"""Daily backup of inbox.db, keeping the last 30 days."""

from __future__ import annotations

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

    # sqlite3 のバックアップAPIで整合性のあるコピーを取る。開いているDBを
    # shutil.copy で生コピーすると、WALやジャーナルが未反映のまま/破損状態で
    # 写り、復元不能なバックアップになりうる。conn.backup はロックを取り
    # 一貫したスナップショットを書く。
    dest = backup_dir / f"inbox-{today}.db"
    with sqlite3.connect(dest) as bck:
        conn.backup(bck)

    # 削除対象は自分のバックアップ命名（inbox-YYYYMMDD.db）だけに限定する。
    # backups/ 内の全ファイルを対象にすると、利用者が退避した手動コピー等も
    # 30日で消してしまう。
    cutoff = datetime.now() - timedelta(days=_KEEP_DAYS)
    for entry in backup_dir.glob("inbox-*.db"):
        if entry.is_file() and datetime.fromtimestamp(entry.stat().st_mtime) < cutoff:
            entry.unlink()

    set_setting(conn, "last_backup_date", today)
