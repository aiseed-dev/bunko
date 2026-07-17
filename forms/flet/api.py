"""HTTP client for the Worker's /items and /ack endpoints. Mirrors api.dart."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import httpx

from db import get_setting


@dataclass
class ApiConfig:
    worker_url: str
    pull_token: str

    @property
    def items_url(self) -> str:
        return f"{self.worker_url}/items"

    @property
    def ack_url(self) -> str:
        return f"{self.worker_url}/ack"


@dataclass
class RemoteItem:
    id: int
    created_at: str
    email: str | None
    payload: str

    @staticmethod
    def from_json(data: dict) -> "RemoteItem":
        raw_payload = data.get("payload")
        payload = raw_payload if isinstance(raw_payload, str) else str(raw_payload)
        return RemoteItem(
            id=data["id"],
            created_at=data["created_at"],
            email=data.get("email"),
            payload=payload,
        )


class ApiError(Exception):
    pass


def load_api_config(conn: sqlite3.Connection) -> ApiConfig | None:
    url = get_setting(conn, "worker_url")
    token = get_setting(conn, "pull_token")
    if url is None or token is None:
        return None
    return ApiConfig(worker_url=url, pull_token=token)


# Server caps a page at 500; keep in sync with the worker.js /items spec.
ITEMS_PAGE_LIMIT = 500


async def fetch_items_page(
    config: ApiConfig, after: int, limit: int = ITEMS_PAGE_LIMIT
) -> list[RemoteItem]:
    """Fetches one page of /items: rows with id > after, ascending, up to limit.
    The caller pages by advancing after to the last id it received."""
    async with httpx.AsyncClient() as client:
        res = await client.get(
            config.items_url,
            params={"after": after, "limit": limit},
            headers={"Authorization": f"Bearer {config.pull_token}"},
            timeout=30,
        )
    if res.status_code != 200:
        raise ApiError(f"/items failed: HTTP {res.status_code}")
    items = res.json().get("items", [])
    return [RemoteItem.from_json(item) for item in items]


async def ack_items(config: ApiConfig, ids: list[int]) -> int:
    if not ids:
        return 0
    async with httpx.AsyncClient() as client:
        res = await client.post(
            config.ack_url,
            headers={"Authorization": f"Bearer {config.pull_token}"},
            json={"ids": ids},
            timeout=30,
        )
    if res.status_code != 200:
        raise ApiError(f"/ack failed: HTTP {res.status_code}")
    return res.json().get("deleted", len(ids))
