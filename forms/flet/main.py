"""FormRescue (Flet) -- pull-based local inbox admin app for a WordPress
contact form decoupled behind a Cloudflare Worker + D1 (or self-hosted)
inbox. See README.md and website/docs/plan/wordpress/todo.md ("管理アプリの
仕様") for the full spec this implements.

Flet 1.0 declarative style: @ft.component + hooks (use_state, use_effect,
use_ref). No routing library and no state-management library -- navigation
between the three screens (setup/settings, list, detail) is a plain
use_state value at the App level.
"""

from __future__ import annotations

from pathlib import Path

import flet as ft

from backup import run_daily_backup_if_needed
from db import get_setting, open_db
from detail_view import DetailView
from help_view import HelpView
from list_view import ListView
from settings_view import SettingsView


async def _data_dir(page: ft.Page) -> Path:
    # StoragePaths は Service なので page.services に登録してから呼ぶ。
    # 未登録のまま await すると "Control must be added to the page first"
    # の RuntimeError で startup ごと死に、ProgressRing のまま固まる。
    storage = ft.StoragePaths()
    page.services.append(storage)
    docs = await storage.get_application_documents_directory()
    return Path(docs) / "data"


@ft.component
def App():
    page = ft.context.page

    conn_ref = ft.use_ref(None)
    ready, set_ready = ft.use_state(False)
    configured, set_configured = ft.use_state(False)
    screen, set_screen = ft.use_state("list")  # "list" | "settings" | "detail"
    selected_remote_id, set_selected_remote_id = ft.use_state(None)
    show_help, set_show_help = ft.use_state(False)

    async def startup():
        data_dir = await _data_dir(page)
        conn = open_db(data_dir)
        conn_ref.current = conn
        run_daily_backup_if_needed(conn, data_dir)
        has_config = (
            get_setting(conn, "worker_url") is not None
            and get_setting(conn, "pull_token") is not None
        )
        set_configured(has_config)
        set_ready(True)

    ft.use_effect(startup, dependencies=[])

    if not ready:
        return ft.Column(
            [ft.ProgressRing()],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
        )

    conn = conn_ref.current

    def open_detail(remote_id: int) -> None:
        set_selected_remote_id(remote_id)
        set_screen("detail")

    def close_detail() -> None:
        set_selected_remote_id(None)
        set_screen("list")

    def finish_initial_setup() -> None:
        set_configured(True)
        set_screen("list")

    if show_help:
        return HelpView(on_back=lambda: set_show_help(False))

    if not configured:
        return SettingsView(
            conn=conn,
            on_saved=finish_initial_setup,
            on_help=lambda: set_show_help(True),
            is_initial_setup=True,
        )

    if screen == "settings":
        return SettingsView(
            conn=conn,
            on_saved=lambda: set_screen("list"),
            on_cancel=lambda: set_screen("list"),
        )

    if screen == "detail" and selected_remote_id is not None:
        return DetailView(conn=conn, remote_id=selected_remote_id, on_back=close_detail)

    return ListView(
        conn=conn,
        on_open_detail=open_detail,
        on_open_settings=lambda: set_screen("settings"),
        on_open_help=lambda: set_show_help(True),
    )


def main(page: ft.Page):
    page.title = "FormRescue"
    page.window.width = 420
    page.window.height = 800
    page.padding = 16
    page.render(App)


ft.run(main)
