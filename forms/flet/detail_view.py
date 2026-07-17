"""Contact detail: formatted payload, confirm (deletes from the remote inbox
via /ack) and handled actions.
"""

from __future__ import annotations

import json
import sqlite3

import flet as ft

from api import ack_items, load_api_config
from db import Contact


def _fetch(conn: sqlite3.Connection, remote_id: int) -> Contact | None:
    row = conn.execute(
        "SELECT * FROM contact WHERE remote_id = ?", (remote_id,)
    ).fetchone()
    return Contact.from_row(row) if row else None


def _fields(payload: str) -> dict:
    try:
        data = json.loads(payload)
        return data if isinstance(data, dict) else {"payload": payload}
    except json.JSONDecodeError:
        return {"payload": payload}


@ft.component
def DetailView(conn: sqlite3.Connection, remote_id: int, on_back):
    version, set_version = ft.use_state(0)
    busy, set_busy = ft.use_state(False)
    error, set_error = ft.use_state("")

    contact = _fetch(conn, remote_id)
    if contact is None:
        return ft.Column(
            [
                ft.Text("この問い合わせは見つかりませんでした"),
                ft.TextButton("戻る", on_click=lambda e: on_back()),
            ]
        )

    async def confirm(e):
        set_busy(True)
        set_error("")
        try:
            # リモートの /ack が先、ローカルの confirmed=1 は成功後。
            # 逆順だと ack 失敗時にボタンが「確認済み」で恒久 disabled になり、
            # 受信箱の行が二度と削除できない（削除経路は /ack のみ）。
            # ack 成功後にローカル更新が失敗しても、再試行の /ack は
            # 削除済み id に対して 0 件削除で冪等に成功する。
            config = load_api_config(conn)
            if config is not None:
                await ack_items(config, [remote_id])
            conn.execute(
                "UPDATE contact SET confirmed = 1 WHERE remote_id = ?", (remote_id,)
            )
            conn.commit()
            set_version(version + 1)
        except Exception as ex:
            set_error(f"確認処理に失敗しました: {ex}")
        finally:
            set_busy(False)

    def mark_handled(e):
        set_busy(True)
        set_error("")
        try:
            conn.execute(
                "UPDATE contact SET handled = 1 WHERE remote_id = ?", (remote_id,)
            )
            conn.commit()
            set_version(version + 1)
        except Exception as ex:
            set_error(f"対応済み処理に失敗しました: {ex}")
        finally:
            set_busy(False)

    field_rows = [
        ft.Column(
            [
                ft.Text(key, weight=ft.FontWeight.BOLD),
                ft.Text(str(value)),
            ],
            spacing=2,
        )
        for key, value in _fields(contact.payload).items()
    ]

    controls = [
        ft.Row(
            [
                ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: on_back()),
                ft.Text("問い合わせ詳細", size=22, weight=ft.FontWeight.BOLD),
            ]
        ),
        ft.Text(f"受付時刻: {contact.created_at}"),
        ft.Container(
            content=ft.Column(field_rows, spacing=10),
            padding=12,
            border=ft.Border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        ),
    ]
    if error:
        controls.append(ft.Text(error, color=ft.Colors.ERROR))
    controls.append(
        ft.FilledButton(
            "確認済み" if contact.confirmed else "確認する",
            icon=ft.Icons.CHECK,
            disabled=busy or contact.confirmed,
            on_click=confirm,
        )
    )
    controls.append(
        ft.Text(
            "確認すると、この問い合わせはCloudflareの受信箱から削除されます。"
            "データはこの端末に残ります。",
            size=12,
        )
    )
    controls.append(
        ft.OutlinedButton(
            "対応済み" if contact.handled else "対応済みにする",
            icon=ft.Icons.TASK_ALT,
            disabled=busy or contact.handled,
            on_click=mark_handled,
        )
    )
    controls.append(
        ft.Text(
            "返信などの対応を終えたら押します。端末内の整理用の印です。",
            size=12,
        )
    )

    return ft.Column(controls, spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)
