"""fonts.py — 外字グリフのサブセット埋め込み（自己完結HTML用）

font モードで使う外字（第3・第4水準など、実Unicode文字）のグリフ**だけ**を
元フォントから切り出して WOFF2 にし、@font-face の data: URI として埋め込む。
これで、閲覧側にJIS X 0213対応フォントが無くても確実に表示され、しかも
埋め込みは数十字ぶんで済む（本文は通常フォントのまま）。

依存は optional の `[font]`（fonttools + brotli）。導入時のみ使う。
"""
from __future__ import annotations

import base64
import glob
import io
import os

# 元フォント候補（Mincho優先・埋め込み可能ライセンス）。無ければ glob で探索。
_CANDIDATES = [
    '/usr/share/fonts/opentype/ipaexfont-mincho/ipaexm.ttf',      # IPAex明朝
    '/usr/share/fonts/opentype/ipafont-mincho/ipam.ttf',          # IPA明朝
    '/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc',    # Noto Serif CJK
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
]
_GLOB_PATTERNS = [
    '/usr/share/fonts/**/ipaexm.ttf',
    '/usr/share/fonts/**/NotoSerifCJK*.ttc',
    '/usr/share/fonts/**/NotoSansCJK*.ttc',
    os.path.expanduser('~/.fonts/**/*.ttf'),
]


def find_source_font() -> str | None:
    """埋め込み用の元フォントを探す（JIS X 0213を広くカバーするもの）。"""
    for p in _CANDIDATES:
        if os.path.exists(p):
            return p
    for pat in _GLOB_PATTERNS:
        hits = sorted(glob.glob(pat, recursive=True))
        if hits:
            return hits[0]
    return None


def subset_woff2(font_path: str, chars: set[str]) -> bytes:
    """元フォントを chars のグリフだけにサブセットし WOFF2 バイト列で返す。"""
    from fontTools import subset
    from fontTools.ttLib import TTFont

    opts = subset.Options()
    opts.flavor = 'woff2'          # brotli 圧縮
    opts.desubroutinize = True
    opts.notdef_outline = True
    opts.recalc_bounds = True
    font = TTFont(font_path, fontNumber=0, lazy=True)
    cmap = font.getBestCmap()
    unicodes = [ord(c) for c in chars if ord(c) in cmap]
    ss = subset.Subsetter(options=opts)
    ss.populate(unicodes=unicodes)
    ss.subset(font)
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


def font_face_css(woff2: bytes, family: str = 'AozoraGaiji',
                  fallback: str = 'serif') -> str:
    """WOFF2 を data: URI 化した @font-face ＋ .gaiji ルールを返す（CRLF）。"""
    b64 = base64.b64encode(woff2).decode('ascii')
    return (f"@font-face {{ font-family: '{family}'; "
            f"src: url(data:font/woff2;base64,{b64}) format('woff2'); }}\r\n"
            f"\t.gaiji {{ font-family: '{family}', {fallback}; }}\r\n")


def _sjis_ok(c: str) -> bool:
    try:
        c.encode('shift_jis')
        return True
    except Exception:
        return False


def gaiji_charset(include_0208: bool = False) -> set[str]:
    """aozorabunko が解決しうる外字の文字集合（Unicode中間表現の全外字）。

    include_0208=False（既定）は Shift_JIS(JIS X 0208)に無い“真の外字”（第3・第4水準等）
    のみ。標準フォントが持たないこの集合を1フォントに収めれば、Flutter/Fletアプリは
    実Unicodeテキストのまま全外字を表示できる（画像も注記も不要）。
    """
    from aozorabunko.gaiji import _table
    chars: set[str] = set()
    for v in _table().values():
        chars.update(v)
    if include_0208:
        return chars
    return {c for c in chars if not _sjis_ok(c)}


def build_gaiji_font(source: str | None = None, out_path: str | None = None,
                     include_0208: bool = False) -> bytes:
    """青空文庫の全外字を収めたサブセットフォント(WOFF2)を作る。アプリ同梱用。"""
    src = source or find_source_font()
    if src is None:
        raise RuntimeError("JIS X 0213対応の元フォントが見つかりません（source=で指定してください）")
    woff2 = subset_woff2(src, gaiji_charset(include_0208))
    if out_path:
        with open(out_path, 'wb') as f:
            f.write(woff2)
    return woff2


if __name__ == '__main__':   # python -m pyaozora.fonts <out.woff2> [--all] [--source PATH]
    import argparse
    ap = argparse.ArgumentParser(description='青空文庫の外字サブセットフォントを作る')
    ap.add_argument('out', help='出力WOFF2パス')
    ap.add_argument('--all', action='store_true',
                    help='JIS X 0208を含む全外字（既定は0208に無い真の外字のみ）')
    ap.add_argument('--source', help='元フォント(ttf/otf/ttc)。省略時は自動探索')
    a = ap.parse_args()
    data = build_gaiji_font(source=a.source, out_path=a.out, include_0208=a.all)
    n = len(gaiji_charset(a.all))
    print(f"wrote {a.out}: {len(data):,} bytes for {n} gaiji chars")
