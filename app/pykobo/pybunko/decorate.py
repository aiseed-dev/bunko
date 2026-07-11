"""decorate.py — 傍点・傍線・圏点・太字などの装飾注記の対応表

COMMAND_TABLE は aozora2html（CC0）の `yml/command_table.yml` を写経したもの（20件・安定）。
各エントリは (CSSクラス名, HTMLタグ)。青空文庫の装飾注記の種別 → 見た目の対応を定める。

記法例:
    ○○［＃「○○」に傍点］        → sesame_dot / em
    ○○［＃「○○」に二重傍線］    → underline_double / em
    ○○［＃「○○」は太字］        → futoji / span
    ○○［＃「○○」の左に傍点］    → sesame_dot_after（左・下は反対側へ）
"""
from __future__ import annotations

# (css_class, html_tag) ── aozora2html yml/command_table.yml 準拠
COMMAND_TABLE: dict[str, tuple[str, str]] = {
    '傍点': ('sesame_dot', 'em'),
    '白ゴマ傍点': ('white_sesame_dot', 'em'),
    '丸傍点': ('black_circle', 'em'),
    '白丸傍点': ('white_circle', 'em'),
    '黒三角傍点': ('black_up-pointing_triangle', 'em'),
    '白三角傍点': ('white_up-pointing_triangle', 'em'),
    '二重丸傍点': ('bullseye', 'em'),
    '蛇の目傍点': ('fisheye', 'em'),
    'ばつ傍点': ('saltire', 'em'),
    '傍線': ('underline_solid', 'em'),
    '二重傍線': ('underline_double', 'em'),
    '鎖線': ('underline_dotted', 'em'),
    '破線': ('underline_dashed', 'em'),
    '波線': ('underline_wave', 'em'),
    '太字': ('futoji', 'span'),
    '斜体': ('shatai', 'span'),
    '下付き小文字': ('subscript', 'sub'),
    '上付き小文字': ('superscript', 'sup'),
    '行右小書き': ('superscript', 'sup'),
    '行左小書き': ('subscript', 'sub'),
}

# 正規表現の種別選択は長いキーを先に（白ゴマ傍点 を 傍点 より先に）
KEYWORDS = sorted(COMMAND_TABLE, key=len, reverse=True)


def deco_class(kind: str, direction: str | None = None) -> tuple[str, str]:
    """種別（＋方向）→ (CSSクラス, HTMLタグ)。

    aozora2html の direction filter を踏襲:
    - 傍点（…点）で 左/下 → クラス末尾に `_after`（反対側に付ける）
    - 傍線（…線）で 左/上 → `under` を `over` に置換（上線化）
    """
    cls, tag = COMMAND_TABLE[kind]
    if direction:
        if '点' in kind and direction in ('左', '下'):
            cls = cls + '_after'
        elif '線' in kind and direction in ('左', '上'):
            cls = cls.replace('under', 'over')
    return cls, tag
