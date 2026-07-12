#!/usr/bin/env python3
"""
aozora_kobo.py — 青空工房（工作員の作業台・Flet）

工作員（入力・校正・保守）向けの統合ツール。Pythonパイプライン
（pybunko）を同一プロセスで直接呼ぶ ── これがFlet採用の理由
（DESIGN.md ADR-4）。3つのタブ:

  検査 …… 作品の変換結果を点検（未対応注記・未解決外字〓・統計・プレビュー）
  校正 …… 作業マニュアル準拠の機械チェック＋Claude校正＋作業履歴の生成
  資産 …… 読者アプリ(bunko)に同梱するデータ資産を作る（書架DB・目次JSON・外字フォント）
  検証 …… pybunko.official の公式XHTML再現を、ミラーの正解HTMLと突き合わせ（diff表示）

実行:  flet run aozora_kobo.py     （Web版: flet run --web aozora_kobo.py）
"""
from __future__ import annotations

import difflib
import re
import urllib.request
from pathlib import Path

import flet as ft

from pybunko import Library, Work, parse
from pybunko.ai import ClaudeClient, locate, proofread
from pybunko.gaiji import resolve_note_body
from pybunko.kosei import lint, work_history

# ================= 意匠（読者アプリと同じ和紙×朱） =================
PAPER, PAPER_HI = '#E7E2D4', '#EEE9DC'
INK, INK_SOFT = '#221F19', '#4A4437'
SHU, MUTED, RULE = '#A8392A', '#8C846E', '#D0C7B1'
OK, WARN = '#3A6B35', '#A8392A'

CACHE = Path('aozora_cache')
_LIB = Library(cache_dir=CACHE)

# ================= コア（GUI非依存・テスト可能） =================

_GAIJI_NOTE_RE = re.compile(r'※［＃([^］]*)］')


def inspect_work(text: str) -> dict:
    """作品テキストの点検レポート。工作員が直すべき箇所を可視化する。"""
    unknown: list[str] = []
    doc = parse(text, unknown_notes=unknown)

    gaiji_notes = _GAIJI_NOTE_RE.findall(text)
    unresolved = [b for b in gaiji_notes if resolve_note_body(b) is None]

    from collections import Counter
    return {
        'doc': doc,
        'stats': {
            '段落': len(doc.paragraphs),
            'ルビ': sum(1 for p in doc.paragraphs for _, r in p.segments if r),
            '見出し': sum(1 for p in doc.paragraphs if p.heading_level),
            '装飾': sum(len(p.decorations or []) for p in doc.paragraphs),
            '挿絵': sum(1 for p in doc.paragraphs if p.image),
            '外字(解決)': len(gaiji_notes) - len(unresolved),
        },
        'unresolved_gaiji': Counter(unresolved),   # 〓 になったもの
        'unknown_notes': Counter(unknown),          # 捨てられた注記
    }


def golden_check(work: Work) -> dict:
    """pybunko.official の公式XHTML再現を、ミラーの正解HTMLとdiff比較。"""
    from pybunko import to_official_html
    card = work.card()
    files = card.get('files', [])
    html_name = None
    for f in files:
        if 'XHTML' in str(f.get('ファイル種別', '')):
            for v in f.values():
                if str(v).endswith('.html'):
                    html_name = v
    if not html_name:
        raise RuntimeError('図書カードにXHTMLファイルの記載がありません')
    base = work.mirror_url.rsplit('/', 1)[0]
    golden = urllib.request.urlopen(f'{base}/{html_name}').read() \
        .decode('shift_jis', errors='replace')
    ours = to_official_html(work.text())

    norm = lambda s: [ln.rstrip() for ln in s.replace('\r\n', '\n').split('\n')]
    g, o = norm(golden), norm(ours)
    sm = difflib.SequenceMatcher(None, g, o)
    diffs = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        diffs.append({'tag': tag, 'golden': g[i1:i2][:3], 'ours': o[j1:j2][:3]})
    return {'ratio': sm.ratio(), 'html_name': html_name,
            'lines': (len(g), len(o)), 'diffs': diffs}


# ================= GUI =================

def main(page: ft.Page):
    page.title = '青空工房 ── 工作員の作業台'
    page.bgcolor = PAPER
    page.padding = 0
    page.fonts = {}

    def status_text(msg: str, color: str = MUTED) -> ft.Text:
        return ft.Text(msg, size=12, color=color)

    # ---------- 検査タブ ----------
    ins_query = ft.TextField(label='作品名・作家名で検索', dense=True, expand=True,
                             bgcolor=PAPER_HI,
                             on_submit=lambda e: ins_search())
    ins_results = ft.ListView(height=180, spacing=2)
    ins_report = ft.ListView(expand=True, spacing=6, padding=10)
    ins_status = status_text('作品を選ぶと、変換結果を点検します')

    def ins_search():
        hits = _LIB.search(ins_query.value or '')
        ins_results.controls = [
            ft.ListTile(
                dense=True,
                title=ft.Text(f'{w.title}', color=INK),
                subtitle=ft.Text(w.author, size=11, color=MUTED),
                on_click=lambda e, w=w: ins_inspect(w))
            for w in hits
        ]
        ins_status.value = f'{len(hits)} 件'
        page.update()

    def ins_inspect(w: Work):
        ins_status.value = f'「{w.title}」を取得・点検中…'
        page.update()
        page.run_thread(lambda: _ins_inspect_work(w))

    def _ins_inspect_work(w: Work):
        try:
            rep = inspect_work(w.text())
        except Exception as ex:
            ins_status.value = f'取得できませんでした: {ex}'
            page.update()
            return
        doc = rep['doc']
        rows: list[ft.Control] = [
            ft.Text(f'{doc.title} ／ {doc.author}', size=18, weight=ft.FontWeight.W_600,
                    color=INK),
            ft.Row([ft.Container(
                ft.Text(f'{k} {v}', size=12,
                        color=INK_SOFT),
                bgcolor=PAPER_HI, border_radius=999,
                padding=ft.Padding(10, 4, 10, 4))
                for k, v in rep['stats'].items()], wrap=True, spacing=6),
        ]
        ung = rep['unresolved_gaiji']
        unk = rep['unknown_notes']
        rows.append(ft.Text(
            f'未解決外字（〓）: {sum(ung.values())} 件',
            color=(WARN if ung else OK), weight=ft.FontWeight.W_600))
        for body, n in ung.most_common(20):
            rows.append(ft.Text(f'  ※［＃{body}］ ×{n}', size=12, color=INK_SOFT,
                                selectable=True))
        rows.append(ft.Text(
            f'未対応注記（除去された）: {sum(unk.values())} 件',
            color=(WARN if unk else OK), weight=ft.FontWeight.W_600))
        for body, n in unk.most_common(30):
            rows.append(ft.Text(f'  ［＃{body}］ ×{n}', size=12, color=INK_SOFT,
                                selectable=True))
        rows.append(ft.Container(height=8))
        rows.append(ft.Text('冒頭プレビュー（ルビは《》表示）', size=12, color=MUTED))
        for p in doc.paragraphs[:8]:
            t = ''.join(f'{s}《{r}》' if r else s for s, r in p.segments)
            rows.append(ft.Text(('　' * p.indent) + t, size=13, color=INK))
        ins_report.controls = rows
        ins_status.value = f'点検完了: {doc.title}'
        page.update()

    tab_inspect = ft.Column([
        ft.Row([ins_query,
                ft.FilledButton('検索', bgcolor=SHU, color=PAPER_HI,
                                on_click=lambda e: ins_search())]),
        ins_status, ins_results, ft.Divider(color=RULE),
        ins_report,
    ], expand=True, spacing=8)

    # ---------- 校正タブ ----------
    # 作業マニュアル【入力編】【校正編】の点検をツール化。
    # 機械チェック=即時（kosei.lint）、Claude校正=意味レベルの疑い（要APIキー）。
    ko_state = {'text': '', 'name': ''}
    ko_path = ft.TextField(label='校正するテキスト（.txt/.zipのパス。Shift_JIS/UTF-8自動）',
                           dense=True, expand=True, bgcolor=PAPER_HI,
                           on_submit=lambda e: ko_load())
    ko_old = ft.Checkbox(label='旧字ファイル（新字の混入も検査）', value=False,
                         label_style=ft.TextStyle(color=INK_SOFT, size=13),
                         active_color=SHU, check_color=PAPER_HI)
    ko_report = ft.ListView(expand=True, spacing=4, padding=10)
    ko_busy = ft.ProgressRing(width=18, height=18, color=SHU, visible=False)
    _claude = ClaudeClient()
    ko_status = status_text(
        'Claude: ' + (f'使用可（{_claude.model}）' if _claude.available
                      else '未設定（環境変数 ANTHROPIC_API_KEY を設定すると使えます）'))

    def ko_load() -> str | None:
        from pybunko.convert import read_text
        try:
            ko_state['text'] = read_text(ko_path.value.strip())
            ko_state['name'] = ko_path.value.strip()
        except Exception as ex:
            ko_status.value = f'読めませんでした: {ex}'
            page.update()
            return None
        return ko_state['text']

    def ko_finding_tile(line, rule, text, note, ai=False):
        return ft.Container(ft.Column([
            ft.Row([ft.Container(
                        ft.Text(('Claude ' if ai else '') + rule, size=11,
                                color=PAPER_HI),
                        bgcolor=(SHU if ai else INK_SOFT), border_radius=999,
                        padding=ft.Padding(8, 2, 8, 2)),
                    ft.Text(f'{line}行' if line else '', size=11, color=MUTED)]),
            ft.Text(text, size=13, color=INK, selectable=True),
            ft.Text(note, size=11, color=MUTED),
        ], spacing=2), bgcolor=PAPER_HI, border_radius=6, padding=8)

    def ko_lint(e):
        text = ko_load()
        if text is None:
            return
        fs = lint(text, old_style=ko_old.value)
        ko_report.controls = [
            ko_finding_tile(f.line, f.rule, f.text, f.note) for f in fs
        ] or [ft.Text('機械チェックは0件です。', color=OK)]
        ko_status.value = (f'機械チェック {len(fs)} 件'
                           '（疑い含む。必ず底本と突き合わせること）')
        page.update()

    def ko_claude(e):
        text = ko_load()
        if text is None:
            return
        if not _claude.available:
            ko_status.value = 'ANTHROPIC_API_KEY が未設定です'
            page.update()
            return
        ko_busy.visible = True
        ko_report.controls = []
        page.update()

        def prog(done, total):
            ko_status.value = f'Claude校正中… {done}/{total} 断片'
            page.update()

        def work():
            try:
                fs = locate(proofread(text, _claude, progress=prog), text)
                ko_report.controls = [
                    ko_finding_tile(f.get('line', 0), '校正の疑い',
                                    f'{f["quote"]}　→　{f.get("suggestion") or "？"}',
                                    f'{f.get("reason", "")}（採否は底本で判断）',
                                    ai=True)
                    for f in fs
                ] or [ft.Text('Claudeからの指摘は0件です。', color=OK)]
                ko_status.value = f'Claude校正完了: {len(fs)} 件の疑い'
            except Exception as ex:
                ko_status.value = f'Claude校正に失敗: {ex}'
            finally:
                ko_busy.visible = False
                page.update()
        page.run_thread(work)

    ko_before = ft.TextField(label='修正前ファイル', dense=True, expand=True,
                             bgcolor=PAPER_HI)
    ko_after = ft.TextField(label='修正後ファイル', dense=True, expand=True,
                            bgcolor=PAPER_HI)

    def ko_history(e):
        from pybunko.convert import read_text
        try:
            h = work_history(read_text(ko_before.value.strip()),
                             read_text(ko_after.value.strip()))
        except Exception as ex:
            ko_status.value = f'読めませんでした: {ex}'
            page.update()
            return
        ko_report.controls = [
            ft.Text('作業履歴（reception宛メールに添えるファイルの下書き）',
                    size=13, weight=ft.FontWeight.W_600, color=INK),
            ft.Container(ft.Text(h, size=13, color=INK, selectable=True,
                                 font_family='monospace'),
                         bgcolor=PAPER_HI, border_radius=6, padding=10),
        ]
        ko_status.value = '作業履歴を作りました（コピーして保存してください）'
        page.update()

    tab_kosei = ft.Column([
        ft.Row([ko_path, ko_busy]),
        ft.Row([
            ft.FilledButton('機械チェック', bgcolor=SHU, color=PAPER_HI,
                            on_click=ko_lint),
            ft.OutlinedButton('Claude校正（意味レベルの疑い）', on_click=ko_claude),
            ko_old,
        ], wrap=True),
        ft.Row([ko_before, ko_after,
                ft.OutlinedButton('作業履歴を生成', on_click=ko_history)]),
        ko_status, ft.Divider(color=RULE),
        ko_report,
    ], expand=True, spacing=8)

    # ---------- 資産タブ ----------
    out_dir = ft.TextField(label='出力先ディレクトリ', value='assets_out',
                           dense=True, bgcolor=PAPER_HI, width=280)
    doc_limit = ft.TextField(label='本文を埋める作品数（0=メタのみ）', value='0',
                             dense=True, bgcolor=PAPER_HI, width=220)
    asset_log = ft.ListView(expand=True, spacing=2, padding=10, auto_scroll=True)
    asset_busy = ft.ProgressRing(width=18, height=18, color=SHU, visible=False)

    def log(msg: str, color: str = INK_SOFT):
        asset_log.controls.append(ft.Text(msg, size=12, color=color, selectable=True))
        page.update()

    def run_asset(name, fn):
        # 重い処理はUIスレッド外で（同期ハンドラで回すとWebSocketが切れて完走しない）
        def work():
            try:
                out = Path(out_dir.value or 'assets_out')
                out.mkdir(parents=True, exist_ok=True)
                fn(out)
            except Exception as ex:
                log(f'✗ {name}: {ex}', WARN)
            finally:
                asset_busy.visible = False
                page.update()

        def handler(e):
            asset_busy.visible = True
            page.update()
            page.run_thread(work)
        return handler

    def build_db(out: Path):
        limit = int(doc_limit.value or 0)
        p = out / 'aozora.db'
        log(f'書架DBを作成中…（本文 {limit} 作品）')
        _LIB.build_sqlite(str(p), documents=limit > 0, cards=limit > 0,
                          limit=(limit if limit > 0 else None))
        from pybunko import db as adb
        st = adb.stats(str(p))
        log(f'✓ {p}: {p.stat().st_size/1024/1024:.1f} MB  {st}', OK)

    def build_index(out: Path):
        p = out / 'index.json'
        log('目次JSONを書き出し中…')
        _LIB.export_index_json(str(p))
        log(f'✓ {p}: {p.stat().st_size/1024:.0f} KB', OK)

    def build_font(out: Path):
        from pybunko import fonts
        p = out / 'aozora-gaiji.woff2'
        log('外字サブセットフォントを生成中…（真の外字4,330字）')
        data = fonts.build_gaiji_font(out_path=str(p))
        log(f'✓ {p}: {len(data)/1024:.0f} KB', OK)

    tab_assets = ft.Column([
        ft.Text('読者アプリ（bunko）に同梱するデータ資産を作ります', color=MUTED, size=13),
        ft.Row([out_dir, doc_limit, asset_busy]),
        ft.Row([
            ft.FilledButton('書架DB（SQLite）', bgcolor=SHU, color=PAPER_HI,
                            on_click=run_asset('書架DB', build_db)),
            ft.OutlinedButton('目次JSON', on_click=run_asset('目次JSON', build_index)),
            ft.OutlinedButton('外字フォント（WOFF2）',
                              on_click=run_asset('外字フォント', build_font)),
        ], wrap=True),
        ft.Divider(color=RULE),
        asset_log,
    ], expand=True, spacing=10)

    # ---------- 検証タブ ----------
    ver_query = ft.TextField(label='作品名で検索（公式XHTMLと突き合わせ）', dense=True,
                             expand=True, bgcolor=PAPER_HI,
                             on_submit=lambda e: ver_search())
    ver_results = ft.ListView(height=160, spacing=2)
    ver_report = ft.ListView(expand=True, spacing=4, padding=10)
    ver_status = status_text('pybunko.official の生成HTMLを、ミラーの正解HTMLとdiff比較します')

    def ver_search():
        hits = _LIB.search(ver_query.value or '')
        ver_results.controls = [
            ft.ListTile(dense=True, title=ft.Text(w.title, color=INK),
                        subtitle=ft.Text(w.author, size=11, color=MUTED),
                        on_click=lambda e, w=w: ver_check(w))
            for w in hits]
        page.update()

    def ver_check(w: Work):
        ver_status.value = f'「{w.title}」を検証中…（正解HTML取得→生成→diff）'
        page.update()
        page.run_thread(lambda: _ver_check_work(w))

    def _ver_check_work(w: Work):
        try:
            rep = golden_check(w)
        except Exception as ex:
            ver_status.value = f'検証できませんでした: {ex}'
            page.update()
            return
        ratio = rep['ratio'] * 100
        exact = not rep['diffs']
        rows: list[ft.Control] = [
            ft.Text(f'{w.title} × {rep["html_name"]}', size=16,
                    weight=ft.FontWeight.W_600, color=INK),
            ft.Text(f'類似度 {ratio:.2f}%'
                    + ('　✓ 完全一致' if exact else f'　相違 {len(rep["diffs"])} ブロック'),
                    color=(OK if ratio > 99.9 else (INK_SOFT if ratio > 95 else WARN)),
                    size=14, weight=ft.FontWeight.W_600),
        ]
        for d in rep['diffs'][:15]:
            rows.append(ft.Container(
                ft.Column([
                    ft.Text(f'[{d["tag"]}]', size=11, color=MUTED),
                    *[ft.Text(f'− 正解: {ln[:90]}', size=11, color=WARN,
                              font_family='monospace') for ln in d['golden']],
                    *[ft.Text(f'＋ 生成: {ln[:90]}', size=11, color=OK,
                              font_family='monospace') for ln in d['ours']],
                ], spacing=1),
                bgcolor=PAPER_HI, border_radius=6, padding=8))
        ver_report.controls = rows
        ver_status.value = f'検証完了: {w.title}（類似 {ratio:.2f}%）'
        page.update()

    tab_verify = ft.Column([
        ft.Row([ver_query,
                ft.FilledButton('検索', bgcolor=SHU, color=PAPER_HI,
                                on_click=lambda e: ver_search())]),
        ver_status, ver_results, ft.Divider(color=RULE),
        ver_report,
    ], expand=True, spacing=8)

    # ---------- 全体 ----------
    header = ft.Container(
        ft.Column([
            ft.Text('青空工房', size=24, weight=ft.FontWeight.W_600, color=INK),
            ft.Text('工作員の作業台 ── 検査・資産づくり・公式HTML検証（Pythonパイプライン直結）',
                    size=12, color=MUTED),
        ], spacing=2),
        padding=ft.Padding(20, 14, 20, 10), bgcolor=PAPER_HI,
    )

    tabs = ft.Tabs(
        length=4,
        expand=True,
        content=ft.Column([
            ft.TabBar(tabs=[ft.Tab(label='検査'), ft.Tab(label='校正'),
                            ft.Tab(label='資産'), ft.Tab(label='検証')],
                      indicator_color=SHU, divider_color=RULE),
            ft.TabBarView(controls=[
                ft.Container(tab_inspect, padding=16),
                ft.Container(tab_kosei, padding=16),
                ft.Container(tab_assets, padding=16),
                ft.Container(tab_verify, padding=16),
            ], expand=True),
        ], expand=True),
    )

    page.add(header, tabs)


if __name__ == '__main__':
    import os
    port = int(os.environ.get('KOBO_PORT', '0'))
    if port:   # Webサーバとして起動（view=WEB_BROWSERでuvicornが立つ。headlessでは開けないだけ）
        ft.run(main, port=port, view=ft.AppView.WEB_BROWSER)
    else:      # 通常のデスクトップ起動
        ft.run(main)
