#!/usr/bin/env python3
"""
aozora_kobo.py — AISeed工房（工作員の作業台・Flet）

工作員（入力・校正・保守）と書き手のための統合ツール ── 昔の日本語
ワープロの現代版（テキストで書き、組版で確かめ、紙とデータに出す）。
Pythonパイプライン（pybunko）を同一プロセスで直接呼ぶ ── これがFlet採用
の理由（DESIGN.md ADR-4）。タブ:

  執筆 …… 青空注記形式で書く。組版プレビュー（washi）・機械チェック・
          印刷PDF・保存（UTF-8／提出用Shift_JIS CR+LF）

  入力 …… 底本ページの写真（スマフォのカメラ可）→ VLMで注記テキストの下書き
  検査 …… 作品の変換結果を点検（未対応注記・未解決外字〓・統計・プレビュー）
          一括点検＝作品を横断して未対応注記の頻度統計（対応の優先順位を決める）
          印刷＝washi組版で縦書きPDF/HTML（禁則・ルビ・縦中横は washi に委譲）
  校正 …… 作業マニュアル準拠の機械チェック＋Claude校正＋作業履歴の生成
  資産 …… 読者アプリ(bunko)に同梱するデータ資産を作る（書架DB・目次JSON・外字フォント）
  検証 …… pybunko.official の公式XHTML再現を、ミラーの正解HTMLと突き合わせ（diff表示）

実行:  flet run aozora_kobo.py     （Web版: flet run --web aozora_kobo.py）
"""
from __future__ import annotations

import difflib
import os
import re
import urllib.request
from pathlib import Path

import flet as ft

from kobo_theme import (BODY, CAPTION, FONT_FAMILY, INK, INK_SOFT, MUTED, OK,
                        PAPER, PAPER_HI, RULE, SHU, SMALL, WARN, make_theme)
from pybunko import Library, Work, parse
from pybunko.ai import ClaudeClient, locate, proofread
from pybunko.gaiji import resolve_note_body
from pybunko.kosei import lint, work_history
from pybunko.vision import ClaudeVisionEngine, OpenAiVisionEngine, transcribe_pages


def finding_tile(line, rule, text, note, ai=False):
    """点検・校正の結果1件を和紙×朱のカードで表示（画面共通）。"""
    return ft.Container(ft.Column([
        ft.Row([ft.Container(
                    ft.Text(('Claude ' if ai else '') + rule, size=CAPTION,
                            color=PAPER_HI),
                    bgcolor=(SHU if ai else INK_SOFT), border_radius=999,
                    padding=ft.Padding(8, 2, 8, 2)),
                ft.Text(f'{line}行' if line else '', size=CAPTION,
                        color=MUTED)]),
        ft.Text(text, size=15, color=INK, selectable=True),
        ft.Text(note, size=CAPTION, color=MUTED),
    ], spacing=2), bgcolor=PAPER_HI, border_radius=6, padding=8)


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
    page.title = 'AISeed工房 ── 工作員の作業台'
    page.fonts = {FONT_FAMILY: 'fonts/ipaexm.ttf'}  # assets/ から（外字込み）
    page.theme = make_theme()
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = PAPER
    page.padding = 0

    def status_text(msg: str, color: str = MUTED) -> ft.Text:
        return ft.Text(msg, size=SMALL, color=color)

    # ---------- 執筆タブ（昔の日本語ワープロ: 書く→組版→刷る） ----------
    ed_picker = ft.FilePicker()
    page.services.append(ed_picker)
    # ファイル名・保存形式・組版モードは画面に出さず内部状態として持つ
    # （メニューの中でだけ扱う ── 昔のワープロの流儀）。
    # 著作権（license）は本文（青空注記テキスト）に行として書く場所が
    # ないため、.pykobo側の付随データとして持つ（title/authorは本文の
    # 1・2行目のまま ── 公式の入力規則を崩さない）。
    # dialect: 'aozora'（青空注記形式・既定）/ 'asciidoc'。AsciiDocは
    # pyasciidoc(pywashiのformat="asciidoc")に丸ごと委譲する別の記法で、
    # pybunko.parse()のDocumentモデルを経由しない（外字注記・字下げ等の
    # 青空注記特有の概念が無いため、変換点検・写真書き起こし・JSON/EPUB
    # 書き出しはaozora専用のまま。要 [asciidoc] エクストラ）。
    ed_state = {'filename': 'draft.pykobo', 'mode': 'normal', 'license': '',
               'dialect': 'aozora'}

    def _ed_get_title_author():
        lines = (ed_text.value or '').split('\n')
        title = lines[0].strip() if len(lines) > 0 else ''
        author = lines[1].strip() if len(lines) > 1 else ''
        return title, author

    def _ed_set_title_author(title, author):
        lines = (ed_text.value or '').split('\n')
        while len(lines) < 2:
            lines.append('')
        lines[0], lines[1] = title, author
        _ed_apply('\n'.join(lines), 0, 0)

    def _update_doc_title():
        # ウェブサイトではないのでバナーは持たず、ウィンドウ/タブのタイトルに
        # 現在のファイル名を出す（普通のエディタと同じ作法）
        page.title = f"{ed_state['filename']} ── AISeed工房"
    _update_doc_title()

    def _washi_opts():
        """組版モード → washi renderの引数と用紙向き。
        ふつう: A4縦・24px ≈ 40字/列。原稿用紙: A4横・24px = マス約6.4mm。"""
        if ed_state['mode'] == 'genko':
            return (dict(vertical=True, genko=True, font_size=24,
                         extra_style='@page{size: A4 landscape;}'),
                    (1123, 794))
        return dict(vertical=True, font_size=24), (794, 1123)
    ed_text = ft.TextField(
        multiline=True, min_lines=24, max_lines=24, expand=True,
        bgcolor=PAPER_HI, text_style=ft.TextStyle(size=16, color=INK),
        hint_text='題名\n著者名\n\n　本文をここに（青空注記形式）…')
    ed_preview = ft.Image(src='', fit=ft.BoxFit.CONTAIN, expand=True)
    # ホイール/ピンチで拡大縮小・ドラッグで移動（PNGは2倍解像度で描画して
    # あるので、拡大しても文字が読める。実機テストの指摘
    # 「プレビューが拡大されない」への対応）
    ed_preview_zoom = ft.InteractiveViewer(
        content=ed_preview, expand=True,
        min_scale=0.5, max_scale=8, scale_enabled=True, pan_enabled=True)
    ed_panel = ft.Container(
        ft.Column([
            ft.Row([
                ft.Text('組版プレビュー（A4・1頁目）', size=CAPTION, color=MUTED,
                        expand=True),
                ft.IconButton(ft.Icons.OPEN_IN_FULL, icon_size=18,
                              icon_color=MUTED,
                              tooltip='パネルを広げる/戻す',
                              on_click=lambda e: _ed_panel_toggle_width()),
                ft.IconButton(ft.Icons.CLOSE, icon_size=18, icon_color=MUTED,
                              tooltip='プレビューを閉じる',
                              on_click=lambda e: _ed_panel_hide()),
            ]),
            ed_preview_zoom,
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        width=360, bgcolor=PAPER_HI, padding=8, border_radius=6,
        visible=False)

    def _ed_panel_hide():
        ed_panel.visible = False
        page.update()

    def _ed_panel_toggle_width():
        ed_panel.width = 760 if ed_panel.width == 360 else 360
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

    def _png_dimensions(data: bytes) -> tuple[int, int] | None:
        """PNGヘッダから幅・高さを読む（依存なし）。PNG以外はNone。"""
        if (len(data) >= 24 and data[:8] == b'\x89PNG\r\n\x1a\n'
                and data[12:16] == b'IHDR'):
            return (int.from_bytes(data[16:20], 'big'),
                    int.from_bytes(data[20:24], 'big'))
        return None

    async def ed_insert_image(e):
        """挿絵を挿入 —— 画像を選び、images/ に保存して注記をカーソル位置に。

        公式のファイル名規則（fig作品ID_通し番号.png、マニュアル4-10）の
        作品IDは公開時に決まるため、ここでは仮の番号（fig0_NN.png）を使う。
        提出前に「入力ファイルへの記載事項」の手順で正式名へリネームする。
        選択していた文字列があればキャプションとして使う。
        """
        files = await ed_picker.pick_files(
            dialog_title='挿絵の画像を選ぶ（PNG推奨）',
            file_type=ft.FilePickerFileType.IMAGE, with_data=True)
        if not files:
            return
        f = files[0]
        data = f.bytes if f.bytes is not None else Path(f.path).read_bytes()
        if not data:
            return
        ed_state['fig_seq'] = ed_state.get('fig_seq', 0) + 1
        filename = f'fig0_{ed_state["fig_seq"]:02d}.png'
        out = Path('images')
        out.mkdir(exist_ok=True)
        (out / filename).write_bytes(data)

        v = _ed_text_get()
        a, b = ed_sel['start'], ed_sel['end']
        a, b = max(0, min(a, len(v))), max(0, min(b, len(v)))
        caption = v[a:b]
        dims = _png_dimensions(data)
        dim_note = f'、横{dims[0]}×縦{dims[1]}' if dims else ''
        ins = f'［＃{caption}（{filename}{dim_note}）入る］'
        _ed_apply(v[:a] + ins + v[b:], a + len(ins), a + len(ins))
        ed_status.value = (f'✓ 画像を images/{filename} に保存し、注記を挿入しました '
                           '── 提出時は作品ID確定後に公式のファイル名へリネーム')
        page.update()

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
        ed_state['filename'] = 'draft.pykobo'
        ed_state['mode'] = 'normal'
        ed_state['license'] = ''
        ed_state['dialect'] = 'aozora'
        for k, mi in mi_mode.items():
            mi.leading = _check(k == 'normal')
        for k, mi in mi_dialect.items():
            mi.leading = _check(k == 'aozora')
        _update_doc_title()
        ed_status.value = '新規作成しました'
        _ed_update_status()
        page.update()

    def ed_show_bibinfo(e):
        """書誌情報（題名・著者・著作権）を別ダイアログで編集。

        題名・著者は本文（青空注記テキスト）の1・2行目そのもの（公式の
        入力規則）。著作権（license）は本文に書く場所がないため.pykobo側の
        付随データ（例 'CC BY 4.0'/'CC0'。空欄=作者に著作権があり無断
        複製・配布不可という既定）。本文編集の最中に紛れ込まないよう、
        通常のエディタ画面とは別のダイアログで扱う。
        """
        title, author = _ed_get_title_author()
        t_field = ft.TextField(label='題名', value=title, autofocus=True)
        a_field = ft.TextField(label='著者', value=author)
        l_field = ft.TextField(
            label='著作権・ライセンス（空欄可）', value=ed_state.get('license', ''),
            hint_text='例: CC BY 4.0 / CC0（空欄=作者に著作権があり無断複製・配布不可）')

        def _apply(ev):
            _ed_set_title_author(t_field.value or '', a_field.value or '')
            ed_state['license'] = l_field.value or ''
            ed_status.value = '書誌情報を更新しました'
            _ed_update_status()
            page.pop_dialog()
            page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text('書誌情報', size=18),
            content=ft.Column([t_field, a_field, l_field], tight=True,
                              width=380, spacing=12),
            actions=[
                ft.TextButton('キャンセル',
                              on_click=lambda ev: page.pop_dialog()),
                ft.FilledButton('反映', on_click=_apply),
            ],
        )
        # Flet 0.85のダイアログAPIは show_dialog/pop_dialog
        # （page.open/page.close は旧0.2x系のAPIで存在しない ──
        # 実機のメニュークリックでAttributeErrorになり発覚）
        page.show_dialog(dlg)

    async def ed_open(e):
        """開く。.pykobo=工房の作業ファイル（構造化・組版モードも復元）／
        .txt・.zip=青空注記テキストの取り込み／.adoc=AsciiDocの取り込み
        （本文だけを読み込む・取り込み後は「.pykobo」として保存し直す前提）。"""
        from pybunko.convert import read_text
        files = await ed_picker.pick_files(
            dialog_title='開く（.pykobo=作業ファイル／.txt・.zip=青空注記／.adoc=AsciiDoc）',
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=['pykobo', 'txt', 'zip', 'adoc'], with_data=True)
        if not files:
            return
        f = files[0]
        try:
            if f.name.endswith('.pykobo'):
                import json as _json
                raw = f.bytes if f.bytes is not None else Path(f.path).read_bytes()
                obj = _json.loads(raw.decode('utf-8'))
                text = obj.get('source', '')
                mode = obj.get('layout_mode', 'normal')
                license_ = obj.get('license', '')
                dialect = obj.get('dialect', 'aozora')
                filename = f.name
            elif f.name.endswith('.adoc'):
                data = f.bytes if f.bytes is not None else Path(f.path).read_bytes()
                text = data.decode('utf-8-sig')
                mode, license_, dialect = 'normal', '', 'asciidoc'
                filename = f'{Path(f.name).stem}.pykobo'
            else:
                if f.bytes is not None:        # Web: バイトで来る
                    import io as _io
                    import zipfile as _zip
                    data = f.bytes
                    if f.name.endswith('.zip') or data[:2] == b'PK':
                        with _zip.ZipFile(_io.BytesIO(data)) as zf:
                            data = zf.read(next(n for n in zf.namelist()
                                                if n.endswith('.txt')))
                    try:
                        text = data.decode('utf-8-sig')
                    except UnicodeDecodeError:
                        text = data.decode('shift_jis', errors='replace')
                else:                          # デスクトップ: パスで来る
                    text = read_text(f.path)
                mode, license_, dialect = 'normal', '', 'aozora'
                filename = f'{Path(f.name).stem}.pykobo'
            ed_state['mode'] = mode if mode in mi_mode else 'normal'
            ed_state['license'] = license_
            ed_state['dialect'] = dialect if dialect in mi_dialect else 'aozora'
            for k, mi in mi_mode.items():
                mi.leading = _check(k == ed_state['mode'])
            for k, mi in mi_dialect.items():
                mi.leading = _check(k == ed_state['dialect'])
            _ed_push_undo()
            ed_text.value = text
            ed_state['filename'] = filename
            _update_doc_title()
            _ed_last_snapshot['v'] = text
            ed_status.value = f'開きました: {f.name}'
            _ed_update_status()
        except Exception as ex:
            ed_status.value = f'開けませんでした: {ex}'
        page.update()

    async def ed_save(e):
        """保存（Ctrl+S）── 構造化データ（.pykobo・JSON）として。

        本文（そのまま）と組版モードを保持する。プレーンテキストでは
        組版モード等の設定が次に開いたときに失われる（形式が崩れる）ため、
        往復（開く・保存）はこの構造化形式で行う。青空文庫への提出用
        プレーンテキストは「エクスポート」から別途書き出す。
        """
        import json as _json
        data = _json.dumps({
            'pykobo_version': 1,
            'source': ed_text.value or '',
            'layout_mode': ed_state['mode'],
            'license': ed_state.get('license', ''),
            'dialect': ed_state.get('dialect', 'aozora'),
        }, ensure_ascii=False, indent=1).encode('utf-8')
        name = ed_state['filename'] or 'draft.pykobo'
        if not name.endswith('.pykobo'):
            name = f'{Path(name).stem}.pykobo'
        path = await ed_picker.save_file(
            dialog_title='名前を付けて保存（工房の作業ファイル）',
            file_name=name,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=['pykobo'],
            src_bytes=data)          # Web: これでブラウザDLになる
        if not path:
            return
        try:
            if not str(path).startswith('upload'):  # デスクトップ: 実パス
                Path(path).write_bytes(data)
            ed_state['filename'] = Path(path).name
            _update_doc_title()
            _ed_last_snapshot['v'] = ed_text.value or ''
            ed_status.value = f'保存しました: {path}（構造化データ・そのまま開き直せます）'
        except Exception as ex:
            ed_status.value = f'保存できませんでした: {ex}'
        page.update()

    def _ed_encode(text, enc):
        """指定エンコードでバイト列へ（Shift_JIS範囲外は例外を投げる）。"""
        if enc == 'sjis':
            return text.replace('\r\n', '\n').replace('\n', '\r\n') \
                .encode('shift_jis')
        return text.encode('utf-8')

    def ed_export_text(enc):
        """青空注記テキスト（提出用）として書き出す ── 一回性のエクスポート。

        こちらは往復（開く・保存）の対象ではない。青空文庫へ提出する
        ときの正規フォーマット（Shift_JIS＋CR+LF、または現代的にUTF-8）
        に変換するだけの出口。
        """
        async def handler(e):
            text = ed_text.value or ''
            if not text.strip():
                return
            if ed_state['dialect'] == 'asciidoc':
                ed_status.value = '青空注記テキストの書き出しは青空注記モード専用です'
                page.update()
                return
            try:
                data = _ed_encode(text, enc)
            except UnicodeEncodeError as ex:
                bad = ex.object[ex.start:ex.start + 1]
                ed_status.value = (f'Shift_JISに無い文字「{bad}」があります ── '
                                   '機械チェックで場所を確認してください')
                page.update()
                return
            base = Path(ed_state['filename'] or 'draft.pykobo').stem
            path = await ed_picker.save_file(
                dialog_title='青空注記テキストとして書き出す（提出用）',
                file_name=f'{base}.txt',
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=['txt'],
                src_bytes=data)
            if not path:
                return
            try:
                if not str(path).startswith('upload'):
                    Path(path).write_bytes(data)
                ed_status.value = f'✓ 青空注記テキスト（{enc}）: {path}'
            except Exception as ex:
                ed_status.value = f'書き出しに失敗: {ex}'
            page.update()
        return handler

    def ed_lint(e):
        fs = lint(ed_text.value or '')
        ed_report.controls = [
            finding_tile(f.line, f.rule, f.text, f.note) for f in fs
        ] or [ft.Text('機械チェックは0件です。', color=OK)]
        ed_status.value = f'機械チェック {len(fs)} 件'
        page.update()

    def _render_washi_html(text: str, opts: dict) -> str:
        """dialectに応じてHTML化する（aozora=pybunko経由・asciidoc=pywashi直結）。"""
        if ed_state['dialect'] == 'asciidoc':
            import pywashi
            return pywashi.render(text, format='asciidoc', **opts)
        from pybunko import parse as _parse
        from pybunko.formats import to_washi_html
        return to_washi_html(_parse(text), **opts)

    def _washi_png(text: str) -> bytes:
        """washi組版の1頁目をPNGに（昔のワープロの印刷プレビュー相当）。

        2倍解像度で描画する ── プレビューをInteractiveViewerで拡大した
        とき文字が潰れないようにするため。--window-sizeはCSSピクセル指定
        なのでそのまま（A4寸法不変）、--force-device-scale-factor=2で
        出力PNGだけが2倍(1588×2246)になる（実測で確認）。
        """
        import subprocess, tempfile
        opts, (w, h) = _washi_opts()
        html = _render_washi_html(text, opts)
        with tempfile.TemporaryDirectory() as td:
            html_p = Path(td) / 'p.html'
            png_p = Path(td) / 'p.png'
            html_p.write_text(html, encoding='utf-8')
            subprocess.run(
                ['google-chrome', '--headless', '--disable-gpu',
                 '--force-device-scale-factor=2',
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
                ed_status.value = '組版プレビューを更新しました（washi・縦書き）'
            except Exception as ex:
                ed_status.value = f'組版に失敗: {ex}'
            finally:
                ed_busy.visible = False
                page.update()
        page.run_thread(work)

    def _ed_asciidoc_title(text: str) -> str:
        """AsciiDocの文書タイトル（先頭の"= "行）。無ければファイル名。"""
        for line in text.split('\n'):
            if line.startswith('= '):
                return line[2:].strip()
        return Path(ed_state['filename']).stem

    def ed_pdf(e):
        text = ed_text.value or ''
        if not text.strip():
            return
        ed_busy.visible = True
        page.update()

        def work():
            try:
                out = Path('print_out')
                out.mkdir(exist_ok=True)
                opts, _ = _washi_opts()
                if ed_state['dialect'] == 'asciidoc':
                    import tempfile
                    import pywashi
                    title = _ed_asciidoc_title(text)
                    safe = ''.join(c for c in (title or 'draft')
                                  if c not in '/\\:*?"<>|')
                    html = pywashi.render(text, format='asciidoc', **opts)
                    with tempfile.NamedTemporaryFile(
                            'w', suffix='.html', delete=False,
                            encoding='utf-8') as f:
                        f.write(html)
                        html_p = Path(f.name)
                    pdf_p = out / f'{safe}.pdf'
                    pywashi.to_pdf(html_p, pdf_p)
                    path = str(pdf_p)
                else:
                    from pybunko import parse as _parse
                    from pybunko.formats import to_pdf
                    doc = _parse(text)
                    safe = ''.join(c for c in (doc.title or 'draft')
                                  if c not in '/\\:*?"<>|')
                    path = to_pdf(doc, str(out / f'{safe}.pdf'), **opts)
                ed_status.value = f'✓ 印刷用PDF: {path}'
            except Exception as ex:
                ed_status.value = f'PDF化に失敗: {ex}'
            finally:
                ed_busy.visible = False
                page.update()
        page.run_thread(work)

    # ── ツール: 今エディタにある文書に対して適用する（別画面は持たない） ──
    def ed_tool_inspect(e):
        """変換点検 —— 未対応注記・未解決外字・統計を下部に出す
        （青空注記専用。外字注記・字下げ等はAsciiDocに無い概念のため）。"""
        if ed_state['dialect'] == 'asciidoc':
            ed_report.controls = [ft.Text(
                '変換点検は青空注記専用です（AsciiDocには外字注記・'
                '未対応注記の概念がありません）。', color=MUTED)]
            ed_status.value = '変換点検はAsciiDocモードでは対象外です'
            page.update()
            return
        rep = inspect_work(ed_text.value or '')
        ung, unk = rep['unresolved_gaiji'], rep['unknown_notes']
        rows = [ft.Text('　'.join(f'{k} {v}' for k, v in rep['stats'].items()),
                        size=15, color=INK)]
        if ung:
            rows.append(ft.Text(f'未解決外字 {sum(ung.values())}件', color=WARN))
            for body, n in ung.most_common(20):
                rows.append(finding_tile(0, '未解決外字',
                                         f'※［＃{body}］×{n}', '外字注記辞書を確認'))
        if unk:
            rows.append(ft.Text(f'未対応注記 {sum(unk.values())}件', color=WARN))
            for body, n in unk.most_common(20):
                rows.append(finding_tile(0, '未対応注記',
                                         f'［＃{body}］×{n}', 'この注記は変換で落ちる'))
        if not ung and not unk:
            rows.append(ft.Text('未対応注記・未解決外字はありません。', color=OK))
        ed_report.controls = rows
        ed_status.value = '変換点検が終わりました（今の文書）'
        page.update()

    def ed_tool_claude(e):
        """Claude校正 —— 今の文書の意味レベルの疑いを下部に出す。"""
        if not _claude.available:
            ed_status.value = 'ANTHROPIC_API_KEY が未設定です'
            page.update()
            return
        text = ed_text.value or ''
        if not text.strip():
            return
        ed_busy.visible = True
        ed_report.controls = []
        page.update()

        def work():
            try:
                from pybunko.ai import locate, proofread
                fs = locate(proofread(text, _claude), text)
                ed_report.controls = [
                    finding_tile(f.get('line', 0), '校正の疑い',
                                 f'{f["quote"]}　→　{f.get("suggestion") or "？"}',
                                 f'{f.get("reason", "")}（採否は底本で判断）',
                                 ai=True)
                    for f in fs
                ] or [ft.Text('Claudeからの指摘は0件です。', color=OK)]
                ed_status.value = f'Claude校正完了: {len(fs)}件の疑い'
            except Exception as ex:
                ed_status.value = f'Claude校正に失敗: {ex}'
            finally:
                ed_busy.visible = False
                page.update()
        page.run_thread(work)

    async def ed_tool_photo(e):
        """写真から書き起こして、今の文書のカーソル位置に取り込む
        （書き起こしは青空注記形式で出るため、青空注記モード専用）。"""
        if ed_state['dialect'] == 'asciidoc':
            ed_status.value = ('写真からの書き起こしは青空注記モード専用です'
                               '（VLMの出力が青空注記形式のため）')
            page.update()
            return
        files = await ed_picker.pick_files(
            dialog_title='底本ページの写真を選ぶ（複数可）',
            file_type=ft.FilePickerFileType.IMAGE,
            allow_multiple=True, with_data=True)
        if not files:
            return
        images = []
        for f in files:
            data = f.bytes
            if data is None and f.path:
                data = Path(f.path).read_bytes()
            if data:
                images.append((f.name, data))
        if not images:
            return
        ed_busy.visible = True
        ed_status.value = f'{len(images)}枚を書き起こし中（ローカルVLM）…'
        page.update()

        def work():
            try:
                base = os.environ.get('AOZORA_VISION_BASE_URL')
                engine = OpenAiVisionEngine(base_url=base)
                text = transcribe_pages(images, engine)
                v = ed_text.value or ''
                a = ed_sel['start']
                _ed_push_undo()
                ed_text.value = v[:a] + text + v[a:]
                ed_status.value = ('書き起こしを取り込みました（下書き ── '
                                   '必ず底本と突き合わせる）')
                _ed_update_status()
            except Exception as ex:
                ed_status.value = (f'書き起こしに失敗: {ex} ── '
                                   'ノード（AOZORA_VISION_BASE_URL）を確認')
            finally:
                ed_busy.visible = False
                page.update()
        page.run_thread(work)

    def _safe_name(title: str, fallback: str = 'draft') -> str:
        return ''.join(c for c in (title or fallback)
                       if c not in '/\\:*?"<>|')

    def ed_export_json(e):
        """構造化データ（Document JSON）として書き出す。

        外字・アクセントは解決済みの実Unicode文字、見出し・字下げ・
        ルビ・装飾・挿絵も構造として保持する一次表現（KUMIHAN.md参照）。
        読者アプリ「文庫」や他のツールがそのまま読み込める。
        """
        text = ed_text.value or ''
        if not text.strip():
            return
        if ed_state['dialect'] == 'asciidoc':
            ed_status.value = ('構造化データ（JSON）書き出しは青空注記モード専用です'
                               '（Documentモデルが青空注記の構造前提のため）')
            page.update()
            return
        try:
            from pybunko import parse as _parse
            doc = _parse(text)
            doc.license = ed_state.get('license', '')
            out = Path('export_out')
            out.mkdir(exist_ok=True)
            path = out / f'{_safe_name(doc.title)}.json'
            path.write_text(doc.to_json(indent=1), encoding='utf-8')
            ed_status.value = f'✓ 構造化データ（JSON）: {path}'
        except Exception as ex:
            ed_status.value = f'JSON化に失敗: {ex}'
        page.update()

    def ed_export_epub(e):
        """EPUB3として書き出す（Send to Kindle・Playブックス等で読める形）。"""
        text = ed_text.value or ''
        if not text.strip():
            return
        if ed_state['dialect'] == 'asciidoc':
            ed_status.value = ('EPUB書き出しは青空注記モード専用です'
                               '（Documentモデルが青空注記の構造前提のため）')
            page.update()
            return
        ed_busy.visible = True
        page.update()

        def work():
            try:
                from pybunko import parse as _parse
                from pybunko.formats import to_epub
                doc = _parse(text)
                out = Path('export_out')
                out.mkdir(exist_ok=True)
                path = to_epub(doc, str(out / f'{_safe_name(doc.title)}.epub'))
                ed_status.value = f'✓ EPUB: {path}'
            except Exception as ex:
                ed_status.value = f'EPUB化に失敗: {ex}'
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

    def _check(on: bool) -> ft.Icon:
        """選択中の項目にだけ✓を出す（未選択も同じ幅を確保して位置を揃える）。"""
        return ft.Icon(ft.Icons.CHECK, size=16,
                      color=SHU if on else 'transparent')

    # 組版モードは選択式メニュー項目（✓が現在値を示す）。
    # 選び直すたびに全項目の✓を更新するので、辞書で持って毎回作り直す。
    mi_mode = {}

    def _set_mode(v):
        def handler(e):
            ed_state['mode'] = v
            for k, mi in mi_mode.items():
                mi.leading = _check(k == v)
            page.update()
        return handler

    mi_mode['normal'] = ft.MenuItemButton(
        content=ft.Text('ふつう（40字/列）', size=15),
        leading=_check(ed_state['mode'] == 'normal'),
        on_click=_set_mode('normal'))
    mi_mode['genko'] = ft.MenuItemButton(
        content=ft.Text('原稿用紙（20×20）', size=15),
        leading=_check(ed_state['mode'] == 'genko'),
        on_click=_set_mode('genko'))

    # 記法（本文の書き方）: 青空注記形式(既定)／AsciiDoc。組版モードとは
    # 独立（AsciiDocでも原稿用紙・縦書きにできる・要[asciidoc]エクストラ）。
    mi_dialect = {}

    def _set_dialect(v):
        def handler(e):
            ed_state['dialect'] = v
            for k, mi in mi_dialect.items():
                mi.leading = _check(k == v)
            page.update()
        return handler

    mi_dialect['aozora'] = ft.MenuItemButton(
        content=ft.Text('青空注記形式', size=15),
        leading=_check(ed_state['dialect'] == 'aozora'),
        on_click=_set_dialect('aozora'))
    mi_dialect['asciidoc'] = ft.MenuItemButton(
        content=ft.Text('AsciiDoc（要 pyasciidoc）', size=15),
        leading=_check(ed_state['dialect'] == 'asciidoc'),
        on_click=_set_dialect('asciidoc'))

    ed_menubar = ft.MenuBar(
        style=ft.MenuStyle(bgcolor=PAPER_HI),
        controls=[
            _menu('ファイル', [
                _mi('新規', ed_new),
                _mi('開く…', ed_open),
                _mi('保存', ed_save, 'Ctrl+S'),
                ft.Divider(height=1, color=RULE),
                _mi('書誌情報（題名・著者・著作権）…', ed_show_bibinfo),
                ft.SubmenuButton(content=ft.Text('記法', size=15),
                                 controls=[mi_dialect['aozora'],
                                          mi_dialect['asciidoc']]),
                ft.Divider(height=1, color=RULE),
                ft.SubmenuButton(content=ft.Text('エクスポート', size=15),
                                 controls=[
                    ft.SubmenuButton(
                        content=ft.Text('青空注記テキスト（提出用）', size=15),
                        controls=[
                            _mi('UTF-8で書き出す…', ed_export_text('utf-8')),
                            _mi('Shift_JIS＋CR+LFで書き出す…',
                                ed_export_text('sjis')),
                        ]),
                    _mi('構造化データ（JSON）', ed_export_json),
                    _mi('EPUB', ed_export_epub),
                ]),
            ]),
            _menu('編集', [
                _mi('元に戻す', _ed_do_undo, 'Ctrl+Z'),
                _mi('やり直す', _ed_do_redo, 'Ctrl+Y'),
                _mi('検索と置換…', _ed_toggle_find),
                ft.Divider(height=1, color=RULE),
                _mi('機械チェック', ed_lint),
            ]),
            _menu('挿入', [
                _mi('ルビ（選択語に）', ed_insert('ruby')),
                _mi('傍点（選択語に）', ed_insert('bouten')),
                _mi('大見出し', ed_insert('midashi')),
                _mi('字下げブロック', ed_insert('jisage')),
                _mi('地付き', ed_insert('jitsuki')),
                _mi('改ページ', ed_insert('kaipage')),
                ft.Divider(height=1, color=RULE),
                _mi('挿絵（画像）…', ed_insert_image),
            ]),
            _menu('レイアウト', [
                mi_mode['normal'], mi_mode['genko'],
                ft.Divider(height=1, color=RULE),
                _mi('組版プレビュー', ed_preview_update),
                _mi('印刷用PDF', ed_pdf),
            ]),
            _menu('ツール', [
                _mi('変換点検（未対応注記・外字）', ed_tool_inspect),
                _mi('Claude校正', ed_tool_claude),
                ft.Divider(height=1, color=RULE),
                _mi('写真から書き起こして取り込む…', ed_tool_photo),
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
        ed_find_row,
        ft.Row([ed_status, ft.Container(expand=True), ed_busy, ed_stat],
               vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ft.Row([
            ft.Container(ed_text, expand=True),
            ed_panel,
        ], expand=True, vertical_alignment=ft.CrossAxisAlignment.START),
        ed_report,
    ], expand=True, spacing=8)

    # ---------- 全体 ----------
    # 普通の日本語ワープロ ── 画面は執筆エディタ一つだけ。メニューの各項目は
    # 「今エディタにある文書」に対して働く（別画面には切り替えない）。
    page.add(
        ft.Container(ft.Row([ed_menubar]), padding=ft.Padding(8, 6, 8, 0)),
        ft.Container(content=tab_write, expand=True, padding=16),
    )


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
