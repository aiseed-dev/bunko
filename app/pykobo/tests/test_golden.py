"""ゴールデンファイル比較 ── 生成HTMLが公式ファイルと一致することを検証。

入力（注記付きテキスト）と正解出力（公式XHTML）の両方が、青空文庫リポジトリ
（aozorabunko/aozorabunko）に存在する。この検証可能性こそ official の核心。
同梱のパブリックドメイン作品で **バイト単位の一致** を担保する。
"""
import io
import pathlib
import zipfile

import pytest

from pybunko import official as converter
from pybunko import to_official_bytes, to_official_html

GOLDEN = pathlib.Path(__file__).parent / "golden"

# (作品名, 入力zip, 正解html) ── いずれもバイト完全一致するPD作品
PAIRS = [
    ("走れメロス", "1567_ruby_4948.zip", "1567_14913.html"),
    ("桜の樹の下には", "427_ruby_19792.zip", "427_19793.html"),
]


def _text(zip_name: str) -> str:
    data = (GOLDEN / zip_name).read_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".txt"))
        return zf.read(name).decode("shift_jis")


@pytest.mark.parametrize("name,zip_name,html_name", PAIRS)
def test_golden_byte_exact(name, zip_name, html_name):
    """注記テキスト → 公式XHTML が Shift_JIS バイト列まで完全一致。"""
    ours = to_official_bytes(_text(zip_name))
    golden = (GOLDEN / html_name).read_bytes()
    assert ours == golden, f"{name}: ours={len(ours)}B golden={len(golden)}B"


def test_official_ruby_format():
    """ルビは公式流儀 <rb>…<rp>（</rp><rt>…</rt><rp>）</rp>。"""
    html = to_official_html(_text("1567_ruby_4948.zip"))
    assert ("<ruby><rb>邪智暴虐</rb><rp>（</rp>"
            "<rt>じゃちぼうぎゃく</rt><rp>）</rp></ruby>") in html


def test_page_skeleton():
    """XHTML1.1 の骨格（DOCTYPE / metadata / main_text / 底本 / 図書カード）。"""
    html = to_official_html(_text("1567_ruby_4948.zip"))
    assert html.startswith('<?xml version="1.0" encoding="Shift_JIS"?>')
    assert '<h1 class="title">走れメロス</h1>' in html
    assert '<div class="main_text">' in html
    assert '<a href="JavaScript:goLibCard();" id="goAZLibCard">●図書カード</a>' in html


def test_gaiji_image_mode():
    """既定（image）では第3・第4水準の外字が公式流儀の <img class="gaiji" /> になる。"""
    # 第3水準 1-91-48 → gaiji/1-91/1-91-48.png（面区点はゼロ詰め、altは注記そのまま）
    img = converter._gaiji_image("「埒のつくり＋虎」、第3水準1-91-48")
    assert img == ('<img src="../../../gaiji/1-91/1-91-48.png" '
                   'alt="※(「埒のつくり＋虎」、第3水準1-91-48)" class="gaiji" />')
    html = to_official_html("題\n著\n\n袁※［＃「にんべん＋參」、第4水準2-1-79］は\n")
    assert '<img src="../../../gaiji/2-01/2-01-79.png"' in html
    assert 'class="gaiji" />は' in html


def test_gaiji_font_mode():
    """gaiji='font' では外字が実Unicode文字（画像でなく <span class="gaiji">）になる。"""
    # 面区点 1-06-75 → 雪だるま ☃（aozorabunko の解決を利用）
    assert converter._gaiji_font("「雪だるま」、1-06-75") == '<span class="gaiji">☃</span>'
    html = to_official_html(
        "題\n著\n\n袁※［＃「にんべん＋參」、第4水準2-1-79］は\n", gaiji='font')
    assert '<img' not in html                      # 画像は使わない
    assert '<span class="gaiji">' in html          # 実文字を span で
    assert '.gaiji { font-family:' in html         # JIS X 0213 対応フォント指定
