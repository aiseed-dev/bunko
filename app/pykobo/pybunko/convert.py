"""convert.py — Shift_JIS 注記付きテキスト → Unicode → JSON（永続パイプラインの入口）

青空文庫の正本は Shift_JIS の注記付きテキスト。これを Unicode に解決した
構造化データ（Document）に変換し、JSON として書き出す一連の流れを、
1関数・1コマンドで使えるようにする。以後の追加作業は、この入口の下流
（parser.py の注記対応、formats.py の出力形式）へ足していけばよい。

    # コード
    from pybunko.convert import to_json
    to_json('1567_ruby_4948.zip', 'merosu.json')

    # CLI
    python -m pybunko 1567_ruby_4948.zip -o merosu.json
    aozorabunko 1567_ruby_4948.zip            # 標準出力へ
"""
from __future__ import annotations

import io
import zipfile
import urllib.request
from pathlib import Path

from .parser import parse, Document


def read_text(src: str) -> str:
    """注記付きテキストを読む。パス / zip / URL に対応。

    zip の場合は中の .txt を取り出す。文字コードは自動判別:
    UTF-8（BOM可）として正しく読めればそれを、だめなら青空文庫標準の
    Shift_JIS（errors='replace'）で読む。
    """
    if src.startswith(('http://', 'https://')):
        data = urllib.request.urlopen(src, timeout=30).read()
    else:
        data = Path(src).read_bytes()
    if src.endswith('.zip') or data[:2] == b'PK':
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            name = next((n for n in zf.namelist() if n.endswith('.txt')), None)
            if name is None:
                raise ValueError(f'zipに.txtファイルが無い: {src}')
            data = zf.read(name)
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError:
        return data.decode('shift_jis', errors='replace')


def convert(src: str, *, image_base: str = '') -> Document:
    """Shift_JIS 注記付きテキスト（パス/zip/URL）→ Document（Unicode中間表現）。"""
    return parse(read_text(src), image_base=image_base)


def to_json(src: str, out: str | None = None, *,
            indent: int | None = None, image_base: str = '') -> str:
    """Shift_JIS 注記付きテキスト → Unicode JSON 文字列。out 指定でファイルにも書く。"""
    js = convert(src, image_base=image_base).to_json(indent=indent)
    if out:
        Path(out).write_text(js, encoding='utf-8')
    return js
