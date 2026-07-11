"""accent.py — 欧文アクセント分解の解決

亀甲括弧内のアクセント記法 `〔e'tiquette〕` を Unicode に解決する。
`accent_table.json`（base文字 → 修飾記号 → [面区点code, 名称]）で分解し、
面区点は gaiji の対応表（JIS X 0213 → Unicode）で実文字にする。

例:  〔e'tiquette〕 → étiquette   （e' = アキュートアクセント付きE小文字, U+00E9）

対応表は aozora2html（CC0）の yml/accent_table.yml 由来。
意味構造ファースト方針: 解決できたときだけ亀甲括弧を外して実文字化する。
何も分解できない 〔…〕 はそのまま残す（安全側）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import gaiji

_DATA = Path(__file__).parent / "data" / "accent_table.json"
_TABLE: dict | None = None

_SPAN_RE = re.compile(r"〔([^〕]*)〕")


def _table() -> dict:
    global _TABLE
    if _TABLE is None:
        _TABLE = json.loads(_DATA.read_text(encoding="utf-8"))
    return _TABLE


def _code_to_char(code: str) -> str | None:
    """"1-09/1-09-63" のような code の面区点部分を Unicode 文字へ。"""
    menkuten = code.rsplit("/", 1)[-1]      # 1-09-63
    return gaiji._table().get(menkuten)


def _resolve_span(s: str) -> str:
    """亀甲括弧の中身を解決。base+修飾（＋2つ目の修飾）→ 実文字。"""
    table = _table()
    out, i, n = [], 0, len(s)
    while i < n:
        base = table.get(s[i])
        matched = False
        if base and i + 1 < n:
            sub = base.get(s[i + 1])
            if isinstance(sub, dict) and i + 2 < n:      # 3段（リガチャ等）
                val = sub.get(s[i + 2])
                if val:
                    ch = _code_to_char(val[0])
                    if ch:
                        out.append(ch)
                        i += 3
                        matched = True
            elif isinstance(sub, list):                  # 2段（base+修飾）
                ch = _code_to_char(sub[0])
                if ch:
                    out.append(ch)
                    i += 2
                    matched = True
        if not matched:
            out.append(s[i])
            i += 1
    return "".join(out)


def resolve(text: str) -> str:
    """テキスト中の 〔…〕 アクセント記法を解決して返す。

    分解できたスパンは亀甲括弧を外して実文字に。分解できなければ 〔…〕 のまま。
    """
    def _repl(m: re.Match) -> str:
        inner = m.group(1)
        resolved = _resolve_span(inner)
        return resolved if resolved != inner else m.group(0)

    return _SPAN_RE.sub(_repl, text)
