#!/usr/bin/env python3
"""
aozora2epub.py — 青空文庫の注記付きテキストを EPUB に変換する

`pybunko` ライブラリの利用例。パース・変換ロジックは持たず、
ライブラリに委譲する（＝サーバを増やさない実装の、さらにその上の薄い層）。

使い方:
    python aozora2epub.py <zipのURL or ローカルzip/txt> [出力.epub]

ライブラリが対応する注記（外字・見出し・字下げ・傍点・アクセント・挿絵・ルビ）が
そのまま活きる。`pip install pybunko[epub]` が必要。
"""
import io
import sys
import zipfile
import urllib.request
from pathlib import Path

from pybunko import parse


def load_text(src: str) -> str:
    """URL / zip / txt から Shift_JIS の注記付きテキストを読み込む。"""
    if src.startswith('http'):
        data = urllib.request.urlopen(src).read()
    else:
        data = Path(src).read_bytes()
    if src.endswith('.zip') or data[:2] == b'PK':
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            name = next(n for n in zf.namelist() if n.endswith('.txt'))
            data = zf.read(name)
    return data.decode('shift_jis', errors='replace')


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    src = argv[0]
    doc = parse(load_text(src))            # 注記付きテキスト → Document
    out = argv[1] if len(argv) > 1 else f'{doc.title}.epub'
    doc.to_epub(out)                       # Document → EPUB3
    print(f'✓ {doc.title} / {doc.author} → {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
