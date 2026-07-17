"""Help / about screen. Same content as the Flutter app's help_screen.dart --
the distributed app doubles as the manual, so the explanation lives in-app.
"""

from __future__ import annotations

import flet as ft

_SECTIONS: list[tuple[str | None, str]] = [
    (
        None,
        "FormRescue は、WordPressの問い合わせフォームに届いたデータを、"
        "Cloudflare上の受信箱から自分の端末に引き取り、手元で確認・管理する"
        "ためのアプリです。データを溜める場所をWordPressから切り離すことで、"
        "サイトが攻撃されても顧客データを失わない状態を作ります。",
    ),
    (
        "データの流れ",
        "1. 訪問者がサイトの問い合わせフォームから送信する\n"
        "2. データはWordPressには残らず、Cloudflareの受信箱に一時保存される\n"
        "3. このアプリが受信箱から取得し、この端末の中に保存する\n"
        "4. 内容を読んで「確認」すると、受信箱側のデータは削除される\n\n"
        "受信箱からの削除は「確認」操作だけです。自動削除はありません。",
    ),
    (
        "取得のタイミング",
        "アプリ起動時、「取得」ボタン、およびアプリを開いている間は"
        "数時間おきに自動で取得します。",
    ),
    (
        "「確認」と「対応済み」",
        "確認: 内容を読んだ、という印。受信箱から削除され、データはこの端末"
        "だけに残ります。\n"
        "対応済み: 返信などの対応を終えた、という印。端末内の整理用です。",
    ),
    (
        "設定に必要なもの",
        "Worker URL と PULL_TOKEN の二つ。どちらも受信箱を設置したとき"
        "(deploy.py または cf-publish の実行時)に表示されます。"
        "QRコードを読み取れば手入力は不要です(Android/iOS版)。",
    ),
    (
        "データの保存場所",
        "取得したデータは、この端末の中のアプリ専用データベース(SQLite)に"
        "だけ保存されます。クラウドには置かれません。起動時に1日1回バック"
        "アップを作成し、直近30日分を保持します。",
    ),
]


@ft.component
def HelpView(on_back):
    controls = [
        ft.Row(
            [
                ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: on_back()),
                ft.Text("このアプリについて", size=22, weight=ft.FontWeight.BOLD),
            ]
        ),
    ]
    for title, body in _SECTIONS:
        if title is not None:
            controls.append(
                ft.Text(title, size=16, weight=ft.FontWeight.BOLD)
            )
        controls.append(ft.Text(body))
    return ft.Column(controls, spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)
