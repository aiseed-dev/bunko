"""Pull sync: fetch remote items and dedupe into the local `contact` table."""

from __future__ import annotations

import sqlite3

from api import ITEMS_PAGE_LIMIT, ApiConfig, fetch_items_page


async def pull_items(conn: sqlite3.Connection, config: ApiConfig) -> int:
    # Start after the highest remote_id we already hold, then page forward until
    # a short page signals the inbox is drained. This survives an inbox far
    # larger than one response, since /items caps each page at ITEMS_PAGE_LIMIT.
    row = conn.execute("SELECT MAX(remote_id) AS m FROM contact").fetchone()
    after = row["m"] if row and row["m"] is not None else 0
    inserted = 0

    while True:
        page = await fetch_items_page(config, after)
        if not page:
            break
        for item in page:
            cur = conn.execute(
                "INSERT OR IGNORE INTO contact "
                "(remote_id, created_at, email, payload) VALUES (?, ?, ?, ?)",
                (item.id, item.created_at, item.email, item.payload),
            )
            if cur.rowcount > 0:
                inserted += 1
        conn.commit()

        after = page[-1].id
        if len(page) < ITEMS_PAGE_LIMIT:
            break
    return inserted
