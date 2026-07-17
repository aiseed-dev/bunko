"""Inbox list: 未確認 / 確認済み / 対応済み tabs, with pull sync on mount,
manual refresh, and a background timer while the app is open.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3

import flet as ft

from api import load_api_config
from db import Contact
from sync import pull_items

_SYNC_INTERVAL_SECONDS = 3 * 60 * 60  # a few hours, per spec

_FILTERS = [
    ("未確認", "confirmed = 0"),
    ("確認済み", "confirmed = 1 AND handled = 0"),
    ("対応済み", "handled = 1"),
]


def _query_contacts(conn: sqlite3.Connection, where: str) -> list[Contact]:
    rows = conn.execute(
        f"SELECT * FROM contact WHERE {where} ORDER BY created_at DESC"
    ).fetchall()
    return [Contact.from_row(r) for r in rows]


def _preview(payload: str) -> str:
    try:
        data = json.loads(payload)
        for v in data.values():
            if isinstance(v, str) and v.strip():
                return v
        return ""
    except (json.JSONDecodeError, TypeError):
        return payload


@ft.component
def ListView(conn: sqlite3.Connection, on_open_detail, on_open_settings, on_open_help=None):
    tab_index, set_tab_index = ft.use_state(0)
    _reload_token, set_reload_token = ft.use_state(0)
    syncing, set_syncing = ft.use_state(False)
    sync_error, set_sync_error = ft.use_state("")

    # Refs (not state) so the mount-time effect closure always sees the
    # live values instead of the stale snapshot from its first render.
    busy_ref = ft.use_ref(False)
    timer_task_ref = ft.use_ref(None)

    async def do_sync():
        if busy_ref.current:
            return
        config = load_api_config(conn)
        if config is None:
            return
        busy_ref.current = True
        set_syncing(True)
        try:
            await pull_items(conn, config)
            set_sync_error("")
        except Exception as e:
            set_sync_error(f"取得に失敗しました: {e}")
        finally:
            busy_ref.current = False
            set_syncing(False)
            set_reload_token(lambda t: t + 1)

    async def periodic_loop():
        while True:
            await asyncio.sleep(_SYNC_INTERVAL_SECONDS)
            await do_sync()

    async def setup():
        timer_task_ref.current = asyncio.create_task(periodic_loop())
        await do_sync()

    def cleanup():
        if timer_task_ref.current is not None:
            timer_task_ref.current.cancel()

    ft.use_effect(setup, dependencies=[], cleanup=cleanup)

    _, where = _FILTERS[tab_index]
    contacts = _query_contacts(conn, where)

    header = ft.Row(
        [
            ft.Text("FormRescue", size=22, weight=ft.FontWeight.BOLD, expand=True),
            ft.IconButton(
                ft.Icons.REFRESH,
                tooltip="取得",
                disabled=syncing,
                on_click=lambda e: asyncio.create_task(do_sync()),
            ),
            ft.IconButton(
                ft.Icons.SETTINGS,
                tooltip="設定",
                on_click=lambda e: on_open_settings(),
            ),
        ]
        + (
            [
                ft.IconButton(
                    ft.Icons.HELP_OUTLINE,
                    tooltip="このアプリについて",
                    on_click=lambda e: on_open_help(),
                )
            ]
            if on_open_help is not None
            else []
        )
    )

    # flet 0.85+ の Tabs はコーディネータで、タブ列は TabBar(content=) に置く。
    # 本文はこのコンポーネントが tab_index から自前で描くので TabBarView は
    # 使わない。on_change の e.data が新しいインデックス。
    tabs = ft.Tabs(
        length=len(_FILTERS),
        selected_index=tab_index,
        on_change=lambda e: set_tab_index(int(e.data)),
        content=ft.TabBar(tabs=[ft.Tab(label=f[0]) for f in _FILTERS]),
    )

    if contacts:
        body = ft.ListView(
            controls=[
                ft.ListTile(
                    title=ft.Text(c.email or "(メールアドレスなし)"),
                    subtitle=ft.Text(
                        f"{c.created_at}\n{_preview(c.payload)}",
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    on_click=lambda e, rid=c.remote_id: on_open_detail(rid),
                )
                for c in contacts
            ],
            expand=True,
        )
    else:
        empty_messages = [
            "未確認の問い合わせはありません。\n\n"
            "サイトのフォームから送信があると、起動時・「取得」ボタン・"
            "数時間おきの自動取得で、ここに表示されます。",
            "確認済み(未対応)の問い合わせはありません。",
            "対応済みの問い合わせはありません。",
        ]
        body = ft.Container(
            content=ft.Text(empty_messages[tab_index], text_align=ft.TextAlign.CENTER),
            alignment=ft.Alignment.CENTER,
            padding=24,
            expand=True,
        )

    children = [header, tabs]
    if sync_error:
        children.append(ft.Text(sync_error, color=ft.Colors.ERROR))
    children.append(body)

    return ft.Column(children, expand=True, spacing=8)
