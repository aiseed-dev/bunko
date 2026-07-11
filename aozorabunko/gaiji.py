"""gaiji.py — 外字注記の Unicode 解決

青空文庫の外字注記（`※［＃「木＋若」、第3水準1-85-1］` など）を、
JIS X 0213 面区点 → Unicode の対応表で実文字に解決する。

方針（HANDOFF/CLAUDE.md）:
- 対応表は aozora2html（CC0）由来の `data/jis2ucs.json`（同梱・11,233件）。
  実行時ロードは標準ライブラリ(json)のみ。再生成は tools/build_gaiji_table.py。
- 解決できた外字は**実Unicode文字**として本文に埋める（plain/reading が正しくなる）。
- 解決できない外字（非0213の合成説明など）は 〓(GETA) に置換し、
  本文から欠落させない。意味構造を正とし、公式互換HTML(<img>/notes span)は
  将来 formats.py の compat レンダラで別途扱う。

対応する記法（注記の中身）:
- JIS X 0213 面区点  例 「…」、第3水準1-85-1  /  「…」、1-2-22
- Unicode 直接指定   例 「…」、U+9AD9
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_DATA = Path(__file__).parent / "data" / "jis2ucs.json"
_TABLE: dict[str, str] | None = None

GETA = "〓"  # 〓 未解決外字の代替（伝統的な欠字記号）
_NON_0213 = "非0213外字"

# 面区点  例 1-85-1 / 1-06-75（ゼロ詰め前でも可）。面は 1 または 2。
_MENKUTEN = re.compile(r"([12])-(\d{1,2})-(\d{1,2})")
# Unicode 直接指定  U+XXXX
_UPLUS = re.compile(r"[Uu]\+([0-9A-Fa-f]{4,6})")
# 外字注記全体  ※［＃ …本文… ］
_GAIJI_NOTE = re.compile(r"※［＃(?P<body>[^］]*)］")


def _table() -> dict[str, str]:
    global _TABLE
    if _TABLE is None:
        _TABLE = json.loads(_DATA.read_text(encoding="utf-8"))
    return _TABLE


def lookup_menkuten(men, ku, ten) -> str | None:
    """面・区・点（数値または文字列）→ 対応表の文字。無ければ None。

    aozora2html の `sprintf('%1d-%02d-%02d', ...)` と同じ正規化でキーを作る。
    """
    key = f"{int(men)}-{int(ku):02d}-{int(ten):02d}"
    return _table().get(key)


def resolve_note_body(body: str) -> str | None:
    """外字注記の中身（［＃ と ］ の間）から解決文字を返す。無ければ None。"""
    if _NON_0213 not in body:
        m = _MENKUTEN.search(body)
        if m:
            ch = lookup_menkuten(*m.groups())
            if ch is not None:
                return ch
    m = _UPLUS.search(body)
    if m:
        try:
            return chr(int(m.group(1), 16))
        except ValueError:
            pass
    return None


def resolve(text: str) -> str:
    """テキスト中の外字注記をすべて置換して返す。

    解決できた外字は実Unicode文字に、できなかったものは 〓(GETA) に。
    パーサーの未対応注記除去（［＃…］の一括削除）より**前**に呼ぶこと。
    """
    def _repl(m: re.Match) -> str:
        ch = resolve_note_body(m.group("body"))
        return ch if ch is not None else GETA

    return _GAIJI_NOTE.sub(_repl, text)
