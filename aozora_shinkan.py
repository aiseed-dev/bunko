#!/usr/bin/env python3
"""
aozora_shinkan.py — 青空文庫リーダー「もうひとつの新館」

実行:  flet run aozora_shinkan.py

これは主張ではなく証明です。このアプリが依存するものは、次の2つだけ:
  1. 青空文庫GitHubミラーの作品リストCSV（テキスト）
  2. 同ミラーの注記付きテキストzip
サーバーサイドのロジックはゼロ。データベースもAPIもありません。
一度カタログを取得すれば、作品ファイルもローカルにキャッシュされ、
以後はオフラインでも検索・閲覧できます。

静的なテキストの正本さえ生きていれば、検索も、ルビ付き表示も、
文字サイズ調整も、すべて読者の手元で実現できる──それだけを示すアプリです。

検索・取得・パースは `aozorabunko` ライブラリに委譲しています
（このアプリはライブラリの利用例。外字・アクセントも解決されて表示されます）。
"""
from __future__ import annotations

import flet as ft

from aozorabunko import Library, Work, parse

# ================= データ層（aozorabunko に委譲・自前ロジックを持たない） =================
# 依存はGitHubミラーの静的ファイルのみ。キャッシュはローカルの
# aozora_cache/（同梱デモzip込み）に置き、二度目からオフラインで動く。

Segment = tuple[str, str | None]

_LIB = Library(cache_dir='aozora_cache')


def load_catalog() -> list[Work]:
    """パブリックドメイン全作品（カタログはミラーのCSV一枚・以後キャッシュ）。"""
    return _LIB.works


def search(works: list[Work], q: str, limit: int = 30) -> list[Work]:
    return _LIB.search(q, limit=limit)


def load_work_text(work: Work) -> str:
    return work.text()


def parse_paragraphs(text: str) -> list[list[Segment]]:
    """注記付きテキスト → 段落ごとのセグメント列（ライブラリのパーサに委譲）。"""
    return [p.segments for p in parse(text).paragraphs]


# ================= 表示層（小さな自己完結型コンポーネント） =================

def ruby_unit(base: str, ruby: str, size: float) -> ft.Column:
    return ft.Column(
        [ft.Text(ruby, size=size * 0.45, color=ft.Colors.GREY_700),
         ft.Text(base, size=size)],
        spacing=0, tight=True,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER)


def paragraph_view(segs: list[Segment], size: float) -> ft.Control:
    if all(r is None for _, r in segs):
        return ft.Text(''.join(t for t, _ in segs), size=size, selectable=True)
    units: list[ft.Control] = []
    for text, ruby in segs:
        if ruby:
            units.append(ruby_unit(text, ruby, size))
        else:
            units.extend(ft.Text(ch, size=size) for ch in text)
    return ft.Row(units, wrap=True, spacing=0, run_spacing=6,
                  vertical_alignment=ft.CrossAxisAlignment.END)


def result_tile(work: Work, on_open) -> ft.Control:
    return ft.Container(
        content=ft.Column([
            ft.Text(work.title, size=16, weight=ft.FontWeight.BOLD),
            ft.Text(work.author, size=12, color=ft.Colors.GREY_700),
        ], spacing=2, tight=True),
        padding=10, border_radius=6, ink=True,
        on_click=lambda e: on_open(work))


# ================= アプリ本体 =================

def main(page: ft.Page):
    page.title = '青空文庫リーダー ── サーバー不要の証明'
    page.padding = 16
    font_size = 18.0
    works: list[Work] = []
    current: list[list[Segment]] = []

    status = ft.Text('カタログを読み込み中…', size=12, color=ft.Colors.GREY)
    query = ft.TextField(label='作品名・作家名・よみ で検索', expand=True,
                         dense=True, on_submit=lambda e: do_search())
    results = ft.ListView(expand=True, spacing=4)
    reader = ft.ListView(expand=True, spacing=10, padding=8)
    header = ft.Text('', size=22, weight=ft.FontWeight.BOLD)

    search_view = ft.Column([ft.Row([query, ft.FilledButton('検索', on_click=lambda e: do_search())]),
                             results], expand=True, visible=True)
    reader_view = ft.Column([
        ft.Row([ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: show_search()),
                header,
                ft.Slider(min=12, max=32, value=font_size, width=180,
                          on_change_end=lambda e: change_size(e))]),
        reader], expand=True, visible=False)

    def do_search():
        results.controls = [result_tile(w, open_work)
                            for w in search(works, query.value)]
        status.value = f'{len(results.controls)} 件'
        page.update()

    def open_work(work: Work):
        nonlocal current
        status.value = f'「{work.title}」を取得中…'
        page.update()
        current = parse_paragraphs(load_work_text(work))
        header.value = f'{work.title} ／ {work.author}'
        render_reader()
        search_view.visible, reader_view.visible = False, True
        status.value = (f'{len(current)} 段落 ・ 手元にキャッシュ済み'
                        '（次回からオフラインで開けます）')
        page.update()

    def render_reader():
        reader.controls = [paragraph_view(s, font_size) for s in current]
        page.update()

    def change_size(e):
        nonlocal font_size
        font_size = e.control.value
        render_reader()

    def show_search():
        search_view.visible, reader_view.visible = True, False
        page.update()

    page.add(status, search_view, reader_view)

    works.extend(load_catalog())
    status.value = (f'パブリックドメイン {len(works):,} 作品 ── '
                    'このアプリはGitHubミラーの静的ファイルだけで動いています')
    page.update()


if __name__ == '__main__':
    ft.run(main)
