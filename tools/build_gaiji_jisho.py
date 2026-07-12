#!/usr/bin/env python3
"""build_gaiji_jisho.py — 外字注記辞書 → gaiji_jisho.json（文字→直し方）

青空文庫の「外字注記辞書」（ミラー gaiji_chuki/*.html）を読み、
機械チェック（pybunko.kosei）が「直し方つき」の指摘を出すための
対応表を作る。実行は再生成時のみ（成果物のJSONを同梱する）。

  出力: {文字: {"to": "青", "kind": "包摂適用"}          # 置き換え
         文字: {"note": "※［＃「…」、第3水準1-84-10］"}  # 外字注記をコピー
        }

HTML版に無い項（例:「靑」の包摂適用）はPDF版（gaiji_chuki.pdf）から
補う。PDFのテキスト抽出に pdftotext（poppler-utils）を使う。

使い方:  python tools/build_gaiji_jisho.py [出力パス]
"""
from __future__ import annotations

import html
import json
import re
import sys
import urllib.request
from pathlib import Path

MIRROR = ('https://raw.githubusercontent.com/aozorabunko/aozorabunko/'
          'master/gaiji_chuki/')
PAGES = ['a', 'ka', 'sa', 'ta', 'na', 'ha', 'ma', 'ya', 'ra', 'sonota']

_ENTRY = re.compile(r'<span id="midasimoji">(.*?)</span>(.*)')
_ARROW = re.compile(r'→［(包摂適用|統合適用|デザイン差|78互換包摂)　(.*?)］')
_NOTE = re.compile(r'※［＃.*?］')
_TAG = re.compile(r'<[^>]+>')


def _plain(fragment: str) -> str:
    return html.unescape(_TAG.sub('', fragment))


def parse_page(text: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for line in text.splitlines():
        m = _ENTRY.search(line)
        if not m:
            continue
        head = _plain(m.group(1)).strip()
        # 「4． 摩」→ 見出し字。字が無い（全角空白だけ）行は対象外
        parts = head.split('．', 1)
        ch = parts[1].strip() if len(parts) == 2 else ''
        if len(ch) != 1 or ch == '　':
            continue
        rest = _plain(m.group(2))
        entry: dict | None = None
        a = _ARROW.search(rest)
        if a and a.group(2).strip():
            entry = {'to': a.group(2).strip(), 'kind': a.group(1)}
        else:
            n = _NOTE.search(rest)
            if n:
                entry = {'note': n.group(0)}
        if entry is None:
            continue
        # 同じ字が複数箇所に載ることがある。置き換え > 面区点つき注記 >
        # ページ数-行数テンプレの順で良いものを残す
        def rank(e: dict) -> int:
            if 'to' in e:
                return 3
            return 2 if '水準' in e.get('note', '') else 1
        if ch not in out or rank(entry) > rank(out[ch]):
            out[ch] = entry
    return out


_PDF_ENTRY = re.compile(
    r'^(?:★\s*)?\d+．\s*(\S)\s*(※［＃[^］]*］)'
    r'(?:\s*→［(包摂適用|統合適用|デザイン差|78互換包摂)\s*(.+?)］\s*\d*\s*$)?')


def parse_pdf(pdf_bytes: bytes) -> dict[str, dict]:
    """PDF版の本文からエントリを拾う（HTML版の補完用）。"""
    import subprocess, tempfile
    with tempfile.NamedTemporaryFile(suffix='.pdf') as f:
        f.write(pdf_bytes)
        f.flush()
        text = subprocess.run(
            ['pdftotext', '-enc', 'UTF-8', f.name, '-'],
            capture_output=True, check=True).stdout.decode('utf-8')
    out: dict[str, dict] = {}
    for line in text.splitlines():
        m = _PDF_ENTRY.match(line.strip())
        if not m:
            continue
        ch, note, kind, to = m.groups()
        if len(ch) != 1:
            continue
        if kind and to and to.strip():
            # 行末に辞書PDFのページ番号が残ることがある
            clean = re.sub(r'\s*\d+\s*$', '', to.strip())
            if clean and clean != ch:
                out.setdefault(ch, {'to': clean, 'kind': kind})
        elif ch not in out:
            out[ch] = {'note': note}
    return out


def main() -> int:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path(__file__).parent.parent
        / 'app/pykobo/pybunko/data/gaiji_jisho.json')
    table: dict[str, dict] = {}
    for page in PAGES:
        raw = urllib.request.urlopen(f'{MIRROR}{page}.html').read()
        entries = parse_page(raw.decode('shift_jis', errors='replace'))
        table.update({k: v for k, v in entries.items() if k not in table
                      or ('to' in v and 'to' not in table[k])})
        print(f'{page}.html: {len(entries)} entries')
    pdf = parse_pdf(urllib.request.urlopen(f'{MIRROR}gaiji_chuki.pdf').read())
    added = {k: v for k, v in pdf.items()
             if k not in table or ('to' in v and 'to' not in table[k])}
    table.update(added)
    print(f'gaiji_chuki.pdf: {len(pdf)} entries（補完 {len(added)}）')
    # 見出し字と置き換え先が同じ（Unicodeでは統合済み）の項は不要
    table = {k: v for k, v in table.items() if v.get('to') != k}
    out_path.write_text(
        json.dumps(table, ensure_ascii=False, indent=0, sort_keys=True),
        encoding='utf-8')
    kinds = sum(1 for v in table.values() if 'to' in v)
    print(f'→ {out_path}: {len(table)}字（置き換え {kinds} / '
          f'外字注記 {len(table) - kinds}）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
