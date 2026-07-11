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
"""
from __future__ import annotations
import csv
import io
import re
import zipfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import flet as ft

# ================= データ層（依存はGitHubミラーの静的ファイルのみ） =================

MIRROR = 'https://raw.githubusercontent.com/aozorabunko/aozorabunko/master/'
CATALOG_URL = MIRROR + 'index_pages/list_person_all_extended_utf8.zip'
CACHE_DIR = Path('aozora_cache')
CACHE_DIR.mkdir(exist_ok=True)

AOZORA_URL_RE = re.compile(r'https?://www\.aozora\.gr\.jp/(cards/.+)')
RUBY_RE = re.compile(
    r'(?:｜(?P<base1>[^《｜]+)'
    r'|(?P<base2>[\u4E00-\u9FFF\u3005-\u3007\uF900-\uFAFF々〆ヵヶ]+))'
    r'《(?P<ruby>[^》]+)》')
NOTE_RE = re.compile(r'［＃[^］]*］')

Segment = tuple[str, str | None]


@dataclass
class Work:
    title: str
    title_yomi: str
    author: str
    author_yomi: str
    text_url: str

    @property
    def github_url(self) -> str:
        m = AOZORA_URL_RE.match(self.text_url)
        return MIRROR + m.group(1) if m else self.text_url

    @property
    def cache_path(self) -> Path:
        return CACHE_DIR / self.github_url.rsplit('/', 1)[-1]


def fetch(url: str, cache: Path) -> bytes:
    """キャッシュ優先で取得。二度目からはオフラインで動く"""
    if cache.exists():
        return cache.read_bytes()
    data = urllib.request.urlopen(url).read()
    cache.write_bytes(data)
    return data


def load_catalog() -> list[Work]:
    raw = fetch(CATALOG_URL, CACHE_DIR / 'catalog.zip')
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        text = zf.read(zf.namelist()[0]).decode('utf-8-sig')
    works = []
    for row in csv.DictReader(io.StringIO(text)):
        if (row['役割フラグ'] == '著者' and row['テキストファイルURL']
                and row['作品著作権フラグ'] == 'なし'
                and row['人物著作権フラグ'] == 'なし'):
            works.append(Work(
                title=row['作品名'], title_yomi=row['作品名読み'],
                author=f"{row['姓']}{row['名']}",
                author_yomi=f"{row['姓読み']}{row['名読み']}",
                text_url=row['テキストファイルURL']))
    return works


def search(works: list[Work], q: str, limit=30) -> list[Work]:
    q = q.strip()
    if not q:
        return []
    hits = [w for w in works if q in w.title or q in w.title_yomi
            or q in w.author or q in w.author_yomi]
    hits.sort(key=lambda w: (w.title != q, not w.title.startswith(q),
                             w.author != q, w.title_yomi))
    return hits[:limit]


def load_work_text(work: Work) -> str:
    data = fetch(work.github_url, work.cache_path)
    if data[:2] == b'PK':
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            name = next(n for n in zf.namelist() if n.endswith('.txt'))
            data = zf.read(name)
    return data.decode('shift_jis', errors='replace')


def parse_paragraphs(text: str) -> list[list[Segment]]:
    text = text.replace('\r\n', '\n')
    body = '\n'.join(text.split('\n')[2:])
    body = re.sub(r'-{10,}\n【テキスト中に現れる記号について】.*?-{10,}\n',
                  '', body, flags=re.S)
    body = re.split(r'\n底本[：:]', body)[0]
    body = NOTE_RE.sub('', body)

    paragraphs = []
    for line in body.split('\n'):
        if not line.strip():
            continue
        segs, pos = [], 0
        for m in RUBY_RE.finditer(line):
            if m.start() > pos:
                segs.append((line[pos:m.start()], None))
            segs.append((m.group('base1') or m.group('base2'), m.group('ruby')))
            pos = m.end()
        if pos < len(line):
            segs.append((line[pos:], None))
        paragraphs.append(segs)
    return paragraphs


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

    nonlocal_works = load_catalog()
    works.extend(nonlocal_works)
    status.value = (f'パブリックドメイン {len(works):,} 作品 ── '
                    'このアプリはGitHubミラーの静的ファイルだけで動いています')
    page.update()


if __name__ == '__main__':
    ft.run(main)
