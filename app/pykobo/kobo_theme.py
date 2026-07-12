"""kobo_theme.py — AISeed工房のテーマ（Flutter側 theme.dart と対）。

規約: **文字サイズを size= で直書きしない**。ここで定めた意味付き定数
（BODY/SMALL/CAPTION/TITLE）か、テーマ既定（sizeなし=16）を使う。
「字がコマすぎて読めない・クリックできない」を二度と起こさないため、
11px/12px と dense=True は禁止。
"""
from __future__ import annotations

import flet as ft

# ── 和紙×朱のパレット（読者アプリ「文庫」と同じ意匠） ───────────
PAPER, PAPER_HI = '#E7E2D4', '#EEE9DC'
INK, INK_SOFT = '#221F19', '#4A4437'
SHU, MUTED, RULE = '#A8392A', '#8C846E', '#D0C7B1'
OK, WARN = '#3A6B35', '#A8392A'

# ── 意味付きの文字サイズ（px）。これ以外の直書きはしない ────────
TITLE = 22      # 画面・作品の見出し
BODY = 16       # 本文・入力欄（テーマ既定 ＝ sizeなしのText）
SMALL = 14      # 補足・ステータス・一覧の副行
CAPTION = 13    # ラベル・注釈（これ未満は作らない）


FONT_FAMILY = 'IPAexMincho'  # 同梱フォント（page.fonts で登録・完全ローカル）


def make_theme() -> ft.Theme:
    """工房全体のテーマ。sizeを書かないTextが16pxで出るのが要点。
    フォントは同梱のIPAex明朝（外字込み・ネット不要）。"""
    return ft.Theme(
        font_family=FONT_FAMILY,
        color_scheme=ft.ColorScheme(
            primary=SHU,
            on_primary=PAPER_HI,
            secondary=INK_SOFT,
            on_secondary=PAPER_HI,
            surface=PAPER,
            on_surface=INK,
            surface_container_highest=PAPER_HI,
            on_surface_variant=INK_SOFT,
            outline=RULE,
            error=WARN,
        ),
        text_theme=ft.TextTheme(
            body_large=ft.TextStyle(size=BODY + 1, color=INK),
            body_medium=ft.TextStyle(size=BODY, color=INK),
            body_small=ft.TextStyle(size=SMALL, color=INK_SOFT),
            title_large=ft.TextStyle(size=TITLE, color=INK,
                                     weight=ft.FontWeight.W_600),
            title_medium=ft.TextStyle(size=BODY + 2, color=INK,
                                      weight=ft.FontWeight.W_600),
            label_large=ft.TextStyle(size=SMALL + 1, color=INK_SOFT),
            label_medium=ft.TextStyle(size=CAPTION, color=MUTED),
        ),
        visual_density=ft.VisualDensity.COMFORTABLE,
    )
