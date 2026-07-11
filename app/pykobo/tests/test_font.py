"""サブセット埋め込みフォントのテスト（[font] エクストラ）。

font モード＋embed_font で、使う外字のグリフだけを WOFF2 に切り出して
@font-face(data:URI) で埋め込む。fonttools/brotli か元フォントが無ければ skip。
"""
import base64
import io
import re

import pytest

from pybunko import to_official_html
from pybunko import fonts

pytest.importorskip("fontTools")
pytest.importorskip("brotli")

_SRC = fonts.find_source_font()
pytestmark = pytest.mark.skipif(_SRC is None, reason="JIS X 0213 元フォントが無い")

# 面区点 1-06-75 → 雪だるま ☃（多くのCJKフォントが持つ）
_DOC = "題\n著\n\n序に※［＃「雪だるま」、1-06-75］が降る。\n"


def test_embed_font_selfcontained():
    html = to_official_html(_DOC, gaiji='font', embed_font=True)
    assert '@font-face' in html
    assert 'src: url(data:font/woff2;base64,' in html
    assert '<img' not in html                       # 画像は使わない
    assert "font-family: 'AozoraGaiji'" in html


def test_embedded_subset_has_glyph():
    from fontTools.ttLib import TTFont
    html = to_official_html(_DOC, gaiji='font', embed_font=True)
    b64 = re.search(r'base64,([A-Za-z0-9+/=]+)\)', html).group(1)
    woff2 = base64.b64decode(b64)
    sub = TTFont(io.BytesIO(woff2))
    assert 0x2603 in sub.getBestCmap()              # ☃ のグリフが入っている
    # サブセットは小さい（使った字だけ）
    assert len(woff2) < 50_000


def test_font_mode_without_embed_uses_names():
    # embed_font 未指定なら data URI は無く、フォント名指定のみ
    html = to_official_html(_DOC, gaiji='font')
    assert 'data:font/woff2' not in html
    assert '.gaiji { font-family: "IPAmjMincho"' in html


def test_gaiji_charset():
    # アプリ同梱用: Shift_JIS(0208)に無い“真の外字”の集合
    cs = fonts.gaiji_charset()
    assert len(cs) > 3000                     # 第3・第4水準など数千字
    assert all(not fonts._sjis_ok(c) for c in cs)   # すべて0208に無い
    # 0208込みの全外字はさらに多い
    assert len(fonts.gaiji_charset(include_0208=True)) > len(cs)
