#!/usr/bin/env python3
"""
aozora_kobo.py — 青空工房（工作員の作業台・Flet）

工作員（入力・校正・保守）と書き手のための統合ツール ── 昔の日本語
ワープロの現代版（テキストで書き、組版で確かめ、紙とデータに出す）。
Pythonパイプライン（pybunko）を同一プロセスで直接呼ぶ ── これがFlet採用
の理由（DESIGN.md ADR-4）。タブ:

  執筆 …… 青空注記形式で書く。組版プレビュー（washi-md）・機械チェック・
          印刷PDF・保存（UTF-8／提出用Shift_JIS CR+LF）

  入力 …… 底本ページの写真（スマフォのカメラ可）→ VLMで注記テキストの下書き
  検査 …… 作品の変換結果を点検（未対応注記・未解決外字〓・統計・プレビュー）
          一括点検＝作品を横断して未対応注記の頻度統計（対応の優先順位を決める）
          印刷＝washi-md組版で縦書きPDF/HTML（禁則・ルビ・縦中横は washi に委譲）
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

from kobo_theme import (BODY, CAPTION, FONT_FAMILY, INK, INK_SOFT, MUTED, OK,
                        PAPER, PAPER_HI, RULE, SHU, SMALL, TITLE, WARN,
                        make_theme)
from pybunko import Library, Work, parse
from pybunko.ai import ClaudeClient, locate, proofread
from pybunko.gaiji import resolve_note_body
from pybunko.kosei import lint, work_history
from pybunko.vision import ClaudeVisionEngine, OpenAiVisionEngine, transcribe_pages


def lan_url(port: int) -> str:
    """スマフォから開くためのLAN上のURL（見つからなければlocalhost）。"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
        s.close()
    except OSError:
        ip = '127.0.0.1'
    return f'http://{ip}:{port}'

# 意匠（和紙×朱・文字サイズ規約）は kobo_theme.py に集約

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
    page.fonts = {FONT_FAMILY: 'fonts/ipaexm.ttf'}  # assets/ から（外字込み）
    page.theme = make_theme()
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = PAPER
    page.padding = 0

    def status_text(msg: str, color: str = MUTED) -> ft.Text:
        return ft.Text(msg, size=SMALL, color=color)

    # ---------- 検査タブ ----------
    ins_query = ft.TextField(label='作品名・作家名で検索', expand=True,
                             bgcolor=PAPER_HI,
                             on_submit=lambda e: ins_search())
    ins_results = ft.ListView(height=180, spacing=2)
    ins_report = ft.ListView(expand=True, spacing=6, padding=10)
    ins_status = status_text('作品を選ぶと、変換結果を点検します')

    def ins_search():
        hits = _LIB.search(ins_query.value or '')
        ins_results.controls = [
            ft.ListTile(
                
                title=ft.Text(f'{w.title}', color=INK),
                subtitle=ft.Text(w.author, size=CAPTION, color=MUTED),
                on_click=lambda e, w=w: ins_inspect(w))
            for w in hits
        ]
        ins_status.value = f'{len(hits)} 件'
        page.update()

    def ins_inspect(w: Work):
        ins_status.value = f'「{w.title}」を取得・点検中…'
        page.update()
        page.run_thread(lambda: _ins_inspect_work(w))

    def ins_print(fmt: str):
        state = getattr(ins_print, 'state', None)
        if not state:
            return
        doc = state
        ins_status.value = f'{fmt.upper()} を組版中…（washi-md）'
        page.update()

        def work():
            try:
                from pybunko.formats import to_pdf, to_washi_html
                out = Path('print_out')
                out.mkdir(exist_ok=True)
                safe = ''.join(c for c in doc.title if c not in '/\\:*?"<>|')
                if fmt == 'pdf':
                    path = to_pdf(doc, str(out / f'{safe}.pdf'),
                                  vertical=True, font_size=24)
                elif fmt == 'html':
                    path = out / f'{safe}.html'
                    path.write_text(
                        to_washi_html(doc, vertical=True, font_size=24),
                        encoding='utf-8')
                elif fmt == 'epub':
                    from pybunko.formats import to_epub
                    path = to_epub(doc, str(out / f'{safe}.epub'))
                else:  # json（Unicode一次データ）
                    path = out / f'{safe}.json'
                    path.write_text(doc.to_json(), encoding='utf-8')
                ins_status.value = f'✓ 書き出しました: {path}'
            except Exception as ex:
                ins_status.value = f'組版に失敗: {ex}'
            finally:
                page.update()
        page.run_thread(work)

    def _ins_inspect_work(w: Work):
        try:
            rep = inspect_work(w.text())
        except Exception as ex:
            ins_status.value = f'取得できませんでした: {ex}'
            page.update()
            return
        doc = rep['doc']
        ins_print.state = doc
        rows: list[ft.Control] = [
            ft.Row([
                ft.Text(f'{doc.title} ／ {doc.author}', size=20,
                        weight=ft.FontWeight.W_600, color=INK, expand=True),
                ft.OutlinedButton('印刷用PDF（縦書き）',
                                  icon=ft.Icons.PRINT,
                                  on_click=lambda e: ins_print('pdf')),
                ft.OutlinedButton('組版HTML',
                                  on_click=lambda e: ins_print('html')),
                ft.OutlinedButton('EPUB',
                                  on_click=lambda e: ins_print('epub')),
                ft.OutlinedButton('JSON',
                                  on_click=lambda e: ins_print('json')),
            ]),
            ft.Row([ft.Container(
                ft.Text(f'{k} {v}', size=SMALL,
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
            rows.append(ft.Text(f'  ※［＃{body}］ ×{n}', size=SMALL, color=INK_SOFT,
                                selectable=True))
        rows.append(ft.Text(
            f'未対応注記（除去された）: {sum(unk.values())} 件',
            color=(WARN if unk else OK), weight=ft.FontWeight.W_600))
        for body, n in unk.most_common(30):
            rows.append(ft.Text(f'  ［＃{body}］ ×{n}', size=SMALL, color=INK_SOFT,
                                selectable=True))
        rows.append(ft.Container(height=8))
        rows.append(ft.Text('冒頭プレビュー（ルビは《》表示）', size=SMALL, color=MUTED))
        for p in doc.paragraphs[:8]:
            t = ''.join(f'{s}《{r}》' if r else s for s, r in p.segments)
            rows.append(ft.Text(('　' * p.indent) + t, size=15, color=INK))
        ins_report.controls = rows
        ins_status.value = f'点検完了: {doc.title}'
        page.update()

    ins_census_limit = ft.TextField(label='一括点検の作品数', value='300',
                                    width=140, bgcolor=PAPER_HI)
    ins_busy = ft.ProgressRing(width=18, height=18, color=SHU, visible=False)

    def ins_census(e):
        ins_busy.visible = True
        ins_report.controls = []
        page.update()

        def prog(done, total):
            if done % 10 == 0 or done == total:
                ins_status.value = f'一括点検中… {done}/{total} 作品'
                page.update()

        def work():
            try:
                from pybunko.census import census
                rep = census(limit=int(ins_census_limit.value or 300),
                             progress=prog)
                rows = [ft.Text(
                    f"一括点検: {rep['scanned']}作品を走査 ── "
                    f"未対応注記 {len(rep['unknown'])}パターン・"
                    f"未解決外字 {len(rep['gaiji_unresolved'])}パターン",
                    size=15, weight=ft.FontWeight.W_600, color=INK)]
                for x in rep['unknown'][:40]:
                    rows.append(ft.Container(ft.Column([
                        ft.Text(f"［＃{x['pattern']}］　×{x['count']}回"
                                f"／{x['works']}作品",
                                size=15, color=INK, selectable=True),
                        ft.Text(f"例: {x['example'][:80]}",
                                size=CAPTION, color=MUTED),
                    ], spacing=2), bgcolor=PAPER_HI, border_radius=6,
                        padding=8))
                ins_report.controls = rows
                ins_status.value = '一括点検が終わりました（頻度順＝対応の優先順位）'
            except Exception as ex:
                ins_status.value = f'一括点検に失敗: {ex}'
            finally:
                ins_busy.visible = False
                page.update()
        page.run_thread(work)

    tab_inspect = ft.Column([
        ft.Row([ins_query,
                ft.FilledButton('検索', bgcolor=SHU, color=PAPER_HI,
                                on_click=lambda e: ins_search()),
                ft.OutlinedButton('一括点検（未対応注記の統計）',
                                  on_click=ins_census),
                ins_census_limit, ins_busy]),
        ins_status, ins_results, ft.Divider(color=RULE),
        ins_report,
    ], expand=True, spacing=8)

    _claude = ClaudeClient()

    # ---------- 執筆タブ（昔の日本語ワープロ: 書く→組版→刷る） ----------
    ed_path = ft.TextField(label='ファイル（開く/保存）', value='draft.txt',
                           width=320, bgcolor=PAPER_HI)
    ed_enc = ft.Dropdown(
        label='保存形式', width=210, bgcolor=PAPER_HI,
        value='utf-8',
        options=[ft.DropdownOption('utf-8', 'UTF-8'),
                 ft.DropdownOption('sjis', 'Shift_JIS＋CR+LF（提出用）')])
    ed_mode = ft.Dropdown(
        label='組版', width=200, bgcolor=PAPER_HI,
        value='normal',
        options=[ft.DropdownOption('normal', 'ふつう（40字/列）'),
                 ft.DropdownOption('genko', '原稿用紙（20×20）')])

    def _washi_opts():
        """組版モード → washi renderの引数と用紙向き。
        ふつう: A4縦・24px ≈ 40字/列。原稿用紙: A4横・24px = マス約6.4mm。"""
        if ed_mode.value == 'genko':
            return (dict(vertical=True, genko=True, font_size=24,
                         extra_style='@page{size: A4 landscape;}'),
                    (1123, 794))
        return dict(vertical=True, font_size=24), (794, 1123)
    ed_text = ft.TextField(
        multiline=True, min_lines=24, max_lines=24, expand=True,
        bgcolor=PAPER_HI, text_style=ft.TextStyle(size=16, color=INK),
        hint_text='題名\n著者名\n\n　本文をここに（青空注記形式）…')
    ed_preview = ft.Image(src='', fit=ft.BoxFit.CONTAIN, expand=True)
    ed_panel = ft.Container(
        ft.Column([
            ft.Row([
                ft.Text('組版プレビュー（A4・1頁目）', size=CAPTION, color=MUTED,
                        expand=True),
                ft.IconButton(ft.Icons.CLOSE, icon_size=18, icon_color=MUTED,
                              tooltip='プレビューを閉じる',
                              on_click=lambda e: _ed_panel_hide()),
            ]),
            ed_preview,
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        width=360, bgcolor=PAPER_HI, padding=8, border_radius=6,
        visible=False)

    def _ed_panel_hide():
        ed_panel.visible = False
        page.update()
    ed_report = ft.ListView(height=150, spacing=4)
    ed_busy = ft.ProgressRing(width=18, height=18, color=SHU, visible=False)
    ed_status = status_text('青空注記形式で書けます ── 語を選択してルビ/傍点、Ctrl+Sで保存')

    # 選択範囲の追跡（挿入・置換・囲みの基準。普通のエディタと同じ動き）
    ed_sel = {'start': 0, 'end': 0}

    def _on_sel(e):
        try:
            b, x = e.selection.base_offset, e.selection.extent_offset
        except AttributeError:
            return
        if b < 0:
            return
        ed_sel['start'], ed_sel['end'] = min(b, x), max(b, x)
        _ed_update_status()

    def _ed_text_get():
        return ed_text.value or ''

    def _ed_apply(new_text, sel_start, sel_end, push_undo=True):
        """本文を置き換え、カーソル/選択を指定位置へ。"""
        if push_undo:
            _ed_push_undo()
        ed_text.value = new_text
        ed_text.selection = ft.TextSelection(base_offset=sel_start,
                                             extent_offset=sel_end)
        ed_sel['start'], ed_sel['end'] = sel_start, sel_end
        ed_text.focus()
        _ed_update_status()
        page.update()

    def ed_insert(kind):
        """カーソル位置に挿入。選択があれば選択テキストを注記で包む。"""
        def handler(e):
            v = _ed_text_get()
            a, b = ed_sel['start'], ed_sel['end']
            a, b = max(0, min(a, len(v))), max(0, min(b, len(v)))
            sel = v[a:b]
            if kind == 'ruby':
                t = sel or '親文字'
                ins = f'｜{t}《よみ》'
                # 《よみ》の中を選択状態に（すぐ読みを打てる）
                start = a + len(f'｜{t}《')
                _ed_apply(v[:a] + ins + v[b:], start, start + 2)
            elif kind == 'bouten':
                t = sel or '対象'
                ins = f'{t}［＃「{t}」に傍点］'
                _ed_apply(v[:a] + ins + v[b:], a + len(ins), a + len(ins))
            elif kind == 'midashi':
                t = sel or '見出し'
                ins = f'{t}［＃「{t}」は大見出し］'
                _ed_apply(v[:a] + ins + v[b:], a + len(ins), a + len(ins))
            elif kind == 'jisage':
                body = sel or ''
                ins = f'［＃ここから２字下げ］\n{body}\n［＃ここで字下げ終わり］'
                pos = a + len('［＃ここから２字下げ］\n')
                _ed_apply(v[:a] + ins + v[b:], pos, pos + len(body))
            elif kind == 'jitsuki':
                ins = f'［＃地付き］{sel}'
                _ed_apply(v[:a] + ins + v[b:], a + len(ins), a + len(ins))
            else:  # 改ページ（行として挿入）
                head = '' if a == 0 or v[a - 1:a] == '\n' else '\n'
                ins = f'{head}［＃改ページ］\n'
                _ed_apply(v[:a] + ins + v[a:], a + len(ins), a + len(ins))
        return handler

    # ── Undo / Redo（Ctrl+Z / Ctrl+Y。履歴は編集操作と打鍵の節目で積む） ──
    ed_undo, ed_redo = [], []

    def _ed_push_undo():
        ed_undo.append(_ed_text_get())
        if len(ed_undo) > 200:
            ed_undo.pop(0)
        ed_redo.clear()

    def _ed_do_undo(e=None):
        if not ed_undo:
            return
        ed_redo.append(_ed_text_get())
        v = ed_undo.pop()
        ed_text.value = v
        _ed_update_status()
        page.update()

    def _ed_do_redo(e=None):
        if not ed_redo:
            return
        ed_undo.append(_ed_text_get())
        ed_text.value = ed_redo.pop()
        _ed_update_status()
        page.update()

    _ed_last_snapshot = {'v': ''}

    def _on_change(e):
        # 打鍵のまとまり（30字ごと or 改行）で履歴を積む
        v = _ed_text_get()
        prev = _ed_last_snapshot['v']
        if abs(len(v) - len(prev)) >= 30 or v.endswith('\n') != prev.endswith('\n'):
            ed_undo.append(prev)
            if len(ed_undo) > 200:
                ed_undo.pop(0)
            _ed_last_snapshot['v'] = v
        _ed_update_status()
        page.update()

    # ── 検索・置換（編集メニューからトグル表示） ──
    ed_find = ft.TextField(label='検索', width=200, bgcolor=PAPER_HI,
                           on_submit=lambda e: _ed_find_next(None))
    ed_repl = ft.TextField(label='置換', width=200, bgcolor=PAPER_HI)

    def _ed_toggle_find(e=None):
        ed_find_row.visible = not ed_find_row.visible
        if ed_find_row.visible:
            ed_find.focus()
        page.update()

    def _ed_find_next(e):
        v, q = _ed_text_get(), ed_find.value or ''
        if not q:
            return
        i = v.find(q, ed_sel['end'])
        if i < 0:
            i = v.find(q)  # 先頭から折り返し
        if i < 0:
            ed_status.value = f'「{q}」は見つかりません'
            page.update()
            return
        _ed_apply(v, i, i + len(q), push_undo=False)
        line = v.count('\n', 0, i) + 1
        ed_status.value = f'{line}行目に移動（選択中。続けて「次」で次候補へ）'
        page.update()

    def _ed_replace_all(e):
        v, q, r = _ed_text_get(), ed_find.value or '', ed_repl.value or ''
        if not q:
            return
        n = v.count(q)
        if n == 0:
            ed_status.value = f'「{q}」は見つかりません'
            page.update()
            return
        _ed_apply(v.replace(q, r), 0, 0)
        ed_status.value = f'{n}件を置換しました（Ctrl+Zで戻せます）'
        page.update()

    # ── ステータスバー（文字数・行数・カーソル位置） ──
    ed_stat = ft.Text('', size=CAPTION, color=MUTED)

    def _ed_update_status():
        v = _ed_text_get()
        pos = ed_sel['start']
        line = v.count('\n', 0, pos) + 1
        col = pos - (v.rfind('\n', 0, pos) + 1) + 1
        chars = len(v.replace('\n', ''))
        sel_n = ed_sel['end'] - ed_sel['start']
        sel_s = f'　選択 {sel_n}字' if sel_n else ''
        ed_stat.value = (f'{chars:,}字　{v.count(chr(10)) + 1}行　'
                         f'カーソル {line}:{col}{sel_s}')

    # エディタ本体へハンドラを接続（定義順の都合で後付け）
    ed_text.on_selection_change = _on_sel
    ed_text.on_change = _on_change

    # ── キーボードショートカット（Ctrl+S 保存 / Ctrl+Z / Ctrl+Y） ──
    def _on_key(e: ft.KeyboardEvent):
        if not e.ctrl:
            return
        k = (e.key or '').upper()
        if k == 'S':
            ed_save(None)
        elif k == 'Z':
            _ed_do_undo()
        elif k == 'Y':
            _ed_do_redo()
    page.on_keyboard_event = _on_key

    def ed_new(e):
        _ed_push_undo()
        ed_text.value = ''
        ed_path.value = 'draft.txt'
        ed_status.value = '新規作成しました'
        _ed_update_status()
        page.update()

    def ed_open(e):
        from pybunko.convert import read_text
        try:
            ed_text.value = read_text(ed_path.value.strip())
            ed_status.value = f'開きました: {ed_path.value}'
        except Exception as ex:
            ed_status.value = f'開けませんでした: {ex}'
        page.update()

    def ed_save(e):
        try:
            path = Path(ed_path.value.strip())
            text = ed_text.value or ''
            if ed_enc.value == 'sjis':
                data = text.replace('\r\n', '\n').replace('\n', '\r\n')
                path.write_bytes(data.encode('shift_jis'))
            else:
                path.write_text(text, encoding='utf-8')
            _ed_last_snapshot['v'] = text
            ed_status.value = f'保存しました: {path}（{ed_enc.value}）'
        except UnicodeEncodeError as ex:
            ed_status.value = ('Shift_JISに無い文字があります ── '
                               f'機械チェックで場所を確認してください（{ex.object[ex.start:ex.start+1]}）')
        except Exception as ex:
            ed_status.value = f'保存できませんでした: {ex}'
        page.update()

    def ed_lint(e):
        fs = lint(ed_text.value or '')
        ed_report.controls = [
            finding_tile(f.line, f.rule, f.text, f.note) for f in fs
        ] or [ft.Text('機械チェックは0件です。', color=OK)]
        ed_status.value = f'機械チェック {len(fs)} 件'
        page.update()

    def _washi_png(text: str) -> bytes:
        """washi-md組版の1頁目をPNGに（昔のワープロの印刷プレビュー相当）。"""
        import subprocess, tempfile
        from pybunko import parse as _parse
        from pybunko.formats import to_washi_html
        opts, (w, h) = _washi_opts()
        html = to_washi_html(_parse(text), **opts)
        with tempfile.TemporaryDirectory() as td:
            html_p = Path(td) / 'p.html'
            png_p = Path(td) / 'p.png'
            html_p.write_text(html, encoding='utf-8')
            subprocess.run(
                ['google-chrome', '--headless', '--disable-gpu',
                 f'--window-size={w},{h}', f'--screenshot={png_p}',
                 html_p.resolve().as_uri()],
                check=True, capture_output=True)
            return png_p.read_bytes()

    def ed_preview_update(e):
        text = ed_text.value or ''
        if not text.strip():
            ed_status.value = '本文が空です'
            page.update()
            return
        ed_busy.visible = True
        page.update()

        def work():
            try:
                import base64
                png = _washi_png(text)
                ed_preview.src = ('data:image/png;base64,'
                                  + base64.b64encode(png).decode())
                ed_panel.visible = True
                ed_status.value = '組版プレビューを更新しました（washi-md・縦書き）'
            except Exception as ex:
                ed_status.value = f'組版に失敗: {ex}'
            finally:
                ed_busy.visible = False
                page.update()
        page.run_thread(work)

    def ed_pdf(e):
        text = ed_text.value or ''
        if not text.strip():
            return
        ed_busy.visible = True
        page.update()

        def work():
            try:
                from pybunko import parse as _parse
                from pybunko.formats import to_pdf
                doc = _parse(text)
                out = Path('print_out')
                out.mkdir(exist_ok=True)
                safe = ''.join(c for c in (doc.title or 'draft')
                               if c not in '/\\:*?"<>|')
                opts, _ = _washi_opts()
                path = to_pdf(doc, str(out / f'{safe}.pdf'), **opts)
                ed_status.value = f'✓ 印刷用PDF: {path}'
            except Exception as ex:
                ed_status.value = f'PDF化に失敗: {ex}'
            finally:
                ed_busy.visible = False
                page.update()
        page.run_thread(work)

    def _mi(label, on_click, shortcut=''):
        """メニュー項目（右にショートカット表示）。"""
        row = [ft.Text(label, size=15)]
        if shortcut:
            row += [ft.Container(width=24),
                    ft.Text(shortcut, size=CAPTION, color=MUTED)]
        return ft.MenuItemButton(
            content=ft.Row(row, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            on_click=on_click)

    def _menu(label, items):
        return ft.SubmenuButton(
            content=ft.Text(label, size=15), controls=items)

    ed_menubar = ft.MenuBar(
        style=ft.MenuStyle(bgcolor=PAPER_HI),
        controls=[
            _menu('ファイル', [
                _mi('新規', ed_new),
                _mi('開く…', ed_open),
                _mi('保存', ed_save, 'Ctrl+S'),
            ]),
            _menu('編集', [
                _mi('元に戻す', _ed_do_undo, 'Ctrl+Z'),
                _mi('やり直す', _ed_do_redo, 'Ctrl+Y'),
                _mi('検索と置換…', _ed_toggle_find),
            ]),
            _menu('挿入', [
                _mi('ルビ（選択語に）', ed_insert('ruby')),
                _mi('傍点（選択語に）', ed_insert('bouten')),
                _mi('大見出し', ed_insert('midashi')),
                _mi('字下げブロック', ed_insert('jisage')),
                _mi('地付き', ed_insert('jitsuki')),
                _mi('改ページ', ed_insert('kaipage')),
            ]),
            _menu('組版', [
                _mi('組版プレビュー', ed_preview_update),
                _mi('印刷用PDF', ed_pdf),
            ]),
            _menu('校正', [
                _mi('機械チェック', ed_lint),
            ]),
        ])

    ed_find_row = ft.Row([ed_find,
                          ft.OutlinedButton('次', on_click=_ed_find_next),
                          ed_repl,
                          ft.OutlinedButton('すべて置換',
                                            on_click=_ed_replace_all),
                          ft.IconButton(ft.Icons.CLOSE, icon_size=18,
                                        icon_color=MUTED,
                                        on_click=_ed_toggle_find),
                          ], wrap=True, visible=False)

    tab_write = ft.Column([
        ft.Row([ed_menubar, ft.Container(width=10),
                ed_path, ed_enc, ed_mode, ed_busy], wrap=True,
               vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ed_find_row,
        ft.Row([ed_status, ft.Container(expand=True), ed_stat]),
        ft.Row([
            ft.Container(ed_text, expand=True),
            ed_panel,
        ], expand=True, vertical_alignment=ft.CrossAxisAlignment.START),
        ed_report,
    ], expand=True, spacing=8)

    # ---------- 入力タブ ----------
    # 底本ページの写真 → VLM書き起こし（下書き）。スマフォからは工房のURLを
    # 開けばカメラで直接撮れる（pick_files が撮影/ギャラリー選択になる）。
    import os as _os
    in_state = {'images': []}   # [(name, bytes)]
    in_picker = ft.FilePicker()
    page.services.append(in_picker)
    in_engine = ft.Dropdown(
        label='エンジン', width=240, bgcolor=PAPER_HI,
        value='openai',
        options=[ft.DropdownOption('openai', 'ローカルVLM（OpenAI互換ノード）'),
                 ft.DropdownOption('claude', 'Claude（画像入力）')])
    in_base = ft.TextField(
        label='ノードURL（…/v1まで）', width=300, bgcolor=PAPER_HI,
        value=_os.environ.get('AOZORA_VISION_BASE_URL', 'http://127.0.0.1:1234/v1'))
    in_model = ft.TextField(label='モデル名', width=200,
                            bgcolor=PAPER_HI,
                            value=_os.environ.get('AOZORA_VISION_MODEL', ''))
    in_files = ft.Text('画像はまだありません', size=SMALL, color=MUTED)
    in_text = ft.TextField(label='書き起こし（下書き ── 必ず底本と突き合わせる）',
                           multiline=True, min_lines=10, max_lines=24,
                           expand=True, bgcolor=PAPER_HI,
                           text_style=ft.TextStyle(size=15, color=INK))
    in_save = ft.TextField(label='保存先（.txt）', expand=True,
                           bgcolor=PAPER_HI, value='draft.txt')
    in_report = ft.ListView(height=220, spacing=4)
    in_busy = ft.ProgressRing(width=18, height=18, color=SHU, visible=False)
    in_status = status_text(
        f'スマフォからは {lan_url(int(_os.environ.get("KOBO_PORT", "8789")))} '
        'を開くと、カメラで撮ってそのまま送れます')

    async def in_pick(e):
        files = await in_picker.pick_files(
            file_type=ft.FilePickerFileType.IMAGE,
            allow_multiple=True, with_data=True)
        for f in files or []:
            data = f.bytes
            if data is None and f.path:            # デスクトップはパスで来る
                data = Path(f.path).read_bytes()
            if data:
                in_state['images'].append((f.name, data))
        in_files.value = (
            '、'.join(f'{n}（{len(b)/1024:.0f}KB）'
                      for n, b in in_state['images'])
            or '画像はまだありません')
        in_status.value = f'{len(in_state["images"])} ページぶんの画像があります'
        page.update()

    def in_clear(e):
        in_state['images'] = []
        in_files.value = '画像はまだありません'
        page.update()

    def in_transcribe(e):
        if not in_state['images']:
            in_status.value = 'まず画像を選んで（撮って）ください'
            page.update()
            return
        if in_engine.value == 'claude':
            if not _claude.available:
                in_status.value = 'ANTHROPIC_API_KEY が未設定です'
                page.update()
                return
            engine = ClaudeVisionEngine(_claude)
        else:
            engine = OpenAiVisionEngine(base_url=in_base.value.strip(),
                                        model=(in_model.value.strip() or None))
        in_busy.visible = True
        page.update()

        def prog(done, total):
            in_status.value = f'書き起こし中… {done}/{total} ページ'
            page.update()

        def work():
            try:
                text = transcribe_pages(in_state['images'], engine,
                                        progress=prog)
                in_text.value = text
                in_status.value = ('書き起こしました（下書き）。底本と突き合わせて'
                                   '直し、機械チェックへ')
            except Exception as ex:
                in_status.value = f'書き起こしに失敗: {ex}'
            finally:
                in_busy.visible = False
                page.update()
        page.run_thread(work)

    def in_lint(e):
        fs = lint(in_text.value or '')
        in_report.controls = [
            finding_tile(f.line, f.rule, f.text, f.note) for f in fs
        ] or [ft.Text('機械チェックは0件です。', color=OK)]
        in_status.value = f'機械チェック {len(fs)} 件'
        page.update()

    def in_write(e):
        try:
            path = Path(in_save.value.strip())
            path.write_text(in_text.value or '', encoding='utf-8')
            in_status.value = f'保存しました: {path}（校正タブでも使えます）'
        except Exception as ex:
            in_status.value = f'保存できませんでした: {ex}'
        page.update()

    tab_input = ft.Column([
        ft.Row([in_engine, in_base, in_model, in_busy], wrap=True),
        ft.Row([
            ft.FilledButton('撮影・画像を選ぶ', bgcolor=SHU, color=PAPER_HI,
                            on_click=in_pick),
            ft.FilledButton('書き起こす', bgcolor=INK_SOFT, color=PAPER_HI,
                            on_click=in_transcribe),
            ft.OutlinedButton('機械チェック', on_click=in_lint),
            ft.OutlinedButton('画像をクリア', on_click=in_clear),
        ], wrap=True),
        in_files, in_status,
        in_text,
        ft.Row([in_save, ft.OutlinedButton('保存', on_click=in_write)]),
        ft.Divider(color=RULE),
        in_report,
    ], expand=True, spacing=8, scroll=ft.ScrollMode.AUTO)

    # ---------- 校正タブ ----------
    # 作業マニュアル【入力編】【校正編】の点検をツール化。
    # 機械チェック=即時（kosei.lint）、Claude校正=意味レベルの疑い（要APIキー）。
    ko_state = {'text': '', 'name': ''}
    ko_path = ft.TextField(label='校正するテキスト（.txt/.zipのパス。Shift_JIS/UTF-8自動）',
                           expand=True, bgcolor=PAPER_HI,
                           on_submit=lambda e: ko_load())
    ko_old = ft.Checkbox(label='旧字ファイル（新字の混入も検査）', value=False,
                         label_style=ft.TextStyle(color=INK_SOFT, size=15),
                         active_color=SHU, check_color=PAPER_HI)
    ko_report = ft.ListView(expand=True, spacing=4, padding=10)
    ko_busy = ft.ProgressRing(width=18, height=18, color=SHU, visible=False)
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

    def finding_tile(line, rule, text, note, ai=False):
        return ft.Container(ft.Column([
            ft.Row([ft.Container(
                        ft.Text(('Claude ' if ai else '') + rule, size=CAPTION,
                                color=PAPER_HI),
                        bgcolor=(SHU if ai else INK_SOFT), border_radius=999,
                        padding=ft.Padding(8, 2, 8, 2)),
                    ft.Text(f'{line}行' if line else '', size=CAPTION, color=MUTED)]),
            ft.Text(text, size=15, color=INK, selectable=True),
            ft.Text(note, size=CAPTION, color=MUTED),
        ], spacing=2), bgcolor=PAPER_HI, border_radius=6, padding=8)

    def ko_lint(e):
        text = ko_load()
        if text is None:
            return
        fs = lint(text, old_style=ko_old.value)
        ko_report.controls = [
            finding_tile(f.line, f.rule, f.text, f.note) for f in fs
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
                    finding_tile(f.get('line', 0), '校正の疑い',
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

    ko_before = ft.TextField(label='修正前ファイル', expand=True,
                             bgcolor=PAPER_HI)
    ko_after = ft.TextField(label='修正後ファイル', expand=True,
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
                    size=15, weight=ft.FontWeight.W_600, color=INK),
            ft.Container(ft.Text(h, size=15, color=INK, selectable=True,
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
                           bgcolor=PAPER_HI, width=280)
    doc_limit = ft.TextField(label='本文を埋める作品数（0=メタのみ）', value='0',
                             bgcolor=PAPER_HI, width=220)
    asset_log = ft.ListView(expand=True, spacing=2, padding=10, auto_scroll=True)
    asset_busy = ft.ProgressRing(width=18, height=18, color=SHU, visible=False)

    def log(msg: str, color: str = INK_SOFT):
        asset_log.controls.append(ft.Text(msg, size=SMALL, color=color, selectable=True))
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
        from pybunko.ndl import mark_reading_corpus
        n = mark_reading_corpus(str(p))
        st = adb.stats(str(p))
        log(f'✓ {p}: {p.stat().st_size/1024/1024:.1f} MB  {st}  '
            f'読みコーパス {n}作品', OK)

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

    # 朗読パック生成（audio.py のGUI。エンジンはOSSローカルが正道・edgeは暫定）
    ab_title = ft.TextField(label='朗読する作品名（完全一致）',
                            width=260, bgcolor=PAPER_HI)
    ab_engine = ft.Dropdown(
        label='TTSエンジン', width=210, bgcolor=PAPER_HI,
        value='edge',
        options=[ft.DropdownOption('sbv2', 'Style-Bert-VITS2（ノード）'),
                 ft.DropdownOption('voicevox', 'VOICEVOX（ローカル）'),
                 ft.DropdownOption('openai', 'OpenAI互換（ノード）'),
                 ft.DropdownOption('edge', 'edge-tts（クラウド・暫定）')])
    ab_base = ft.TextField(label='ノードURL', width=230,
                           bgcolor=PAPER_HI, value='http://127.0.0.1:5000')
    ab_voice = ft.TextField(label='声（voice/model）', width=180,
                            bgcolor=PAPER_HI)
    ab_limit = ft.TextField(label='段落数（0=全部）', width=140,
                            bgcolor=PAPER_HI, value='0')
    ab_ndl = ft.TextField(label='NDL読み注釈txt（任意）', width=260,
                          bgcolor=PAPER_HI)

    def build_audiobook_asset(out: Path):
        from pybunko.audio import (EdgeEngine, OpenAiSpeechEngine,
                                   StyleBertVits2Engine, VoicevoxEngine,
                                   build_audiobook)
        title = (ab_title.value or '').strip()
        hits = [w for w in _LIB.search(title) if w.title == title]
        if not hits:
            log(f'✗ 作品が見つかりません: {title}', WARN)
            return
        w = hits[0]
        eng = ab_engine.value
        voice = (ab_voice.value or '').strip()
        if eng == 'sbv2':
            engine = StyleBertVits2Engine(ab_base.value, model=voice or 0)
        elif eng == 'voicevox':
            engine = VoicevoxEngine(speaker=int(voice) if voice else 3)
        elif eng == 'openai':
            engine = OpenAiSpeechEngine(ab_base.value, voice=voice or 'alloy')
        else:
            engine = EdgeEngine(voice=voice or 'ja-JP-NanamiNeural')
        readings = None
        if (ab_ndl.value or '').strip():
            from pybunko.ndl import parse_annotation
            readings = parse_annotation(
                Path(ab_ndl.value.strip()).read_text(encoding='utf-8'))
            log(f'NDL読み辞書: {len(readings)}語')
        doc = w.document()
        limit = int(ab_limit.value or 0) or None
        adir = out / 'audiobooks'
        adir.mkdir(parents=True, exist_ok=True)
        base = adir / w.work_id
        log(f'朗読パック合成中: {w.title}（{engine.name}）…')
        m = build_audiobook(
            doc, str(base), engine, limit=limit, readings=readings,
            progress=lambda d, t: log(f'  {d}/{t} 段落') if d % 10 == 0 else None)
        log(f"✓ {base}.opus（{m['total']:.0f}秒・{len(m['paras'])}段落）"
            f" / manifest={base}.audiobook.json", OK)

    tab_assets = ft.Column([
        ft.Text('読者アプリ（bunko）に同梱するデータ資産を作ります', color=MUTED, size=15),
        ft.Row([out_dir, doc_limit, asset_busy]),
        ft.Row([
            ft.FilledButton('書架DB（SQLite）', bgcolor=SHU, color=PAPER_HI,
                            on_click=run_asset('書架DB', build_db)),
            ft.OutlinedButton('目次JSON', on_click=run_asset('目次JSON', build_index)),
            ft.OutlinedButton('外字フォント（WOFF2）',
                              on_click=run_asset('外字フォント', build_font)),
        ], wrap=True),
        ft.Divider(color=RULE),
        ft.Text('朗読パック（音声＋段落タイミング。文庫の audiobooks/ に置くと再生ボタンが出ます）',
                color=MUTED, size=15),
        ft.Row([ab_title, ab_engine, ab_base, ab_voice, ab_limit, ab_ndl,
                ft.FilledButton('朗読パック生成', bgcolor=SHU, color=PAPER_HI,
                                on_click=run_asset('朗読パック',
                                                   build_audiobook_asset)),
                ], wrap=True),
        ft.Divider(color=RULE),
        asset_log,
    ], expand=True, spacing=10)

    # ---------- 検証タブ ----------
    ver_query = ft.TextField(label='作品名で検索（公式XHTMLと突き合わせ）',
                             expand=True, bgcolor=PAPER_HI,
                             on_submit=lambda e: ver_search())
    ver_results = ft.ListView(height=160, spacing=2)
    ver_report = ft.ListView(expand=True, spacing=4, padding=10)
    ver_status = status_text('pybunko.official の生成HTMLを、ミラーの正解HTMLとdiff比較します')

    def ver_search():
        hits = _LIB.search(ver_query.value or '')
        ver_results.controls = [
            ft.ListTile(title=ft.Text(w.title, color=INK),
                        subtitle=ft.Text(w.author, size=CAPTION, color=MUTED),
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
                    size=BODY, weight=ft.FontWeight.W_600),
        ]
        for d in rep['diffs'][:15]:
            rows.append(ft.Container(
                ft.Column([
                    ft.Text(f'[{d["tag"]}]', size=CAPTION, color=MUTED),
                    *[ft.Text(f'− 正解: {ln[:90]}', size=CAPTION, color=WARN,
                              font_family='monospace') for ln in d['golden']],
                    *[ft.Text(f'＋ 生成: {ln[:90]}', size=CAPTION, color=OK,
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
            ft.Text('青空工房', size=TITLE, weight=ft.FontWeight.W_600, color=INK),
            ft.Text('書く・整える・届ける ── 執筆・入力・校正・検査・資産・検証（日本語ワープロ＋工作員の作業台）',
                    size=SMALL, color=MUTED),
        ], spacing=2),
        padding=ft.Padding(20, 14, 20, 10), bgcolor=PAPER_HI,
    )

    tabs = ft.Tabs(
        length=6,
        expand=True,
        content=ft.Column([
            ft.TabBar(tabs=[ft.Tab(label='執筆'), ft.Tab(label='入力'),
                            ft.Tab(label='校正'), ft.Tab(label='検査'),
                            ft.Tab(label='資産'), ft.Tab(label='検証')],
                      indicator_color=SHU, divider_color=RULE,
                      label_text_style=ft.TextStyle(size=15,
                                               weight=ft.FontWeight.W_600),
                      unselected_label_text_style=ft.TextStyle(size=15)),
            ft.TabBarView(controls=[
                ft.Container(tab_write, padding=16),
                ft.Container(tab_input, padding=16),
                ft.Container(tab_kosei, padding=16),
                ft.Container(tab_inspect, padding=16),
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
        # host=0.0.0.0: スマフォ（同一LAN）から開いてカメラで底本を撮るため
        ft.run(main, port=port, view=ft.AppView.WEB_BROWSER,
               host=os.environ.get('KOBO_HOST', '0.0.0.0'),
               assets_dir='assets')
    else:      # 通常のデスクトップ起動
        ft.run(main, assets_dir='assets')
