"""washi-md 連携（縦書き・PDF組版）テスト。

Document → Markdown（dendenルビ）→ washi-md.render の経路を確認する。
washi-md（aiseed-dev, [washi]エクストラ）が入っていなければskip。
これは「一緒にバージョンアップ」する組版レイヤーとの結線点。
"""
import pytest

from aozorabunko import parse

washi_md = pytest.importorskip("washi_md")


def test_to_markdown_ruby():
    # ルビは denden 記法 {base|reading} に
    doc = parse("題\n著\n\n邪智暴虐《じゃちぼうぎゃく》の王。\n")
    md = doc.to_markdown()
    assert "{邪智暴虐|じゃちぼうぎゃく}" in md


def test_to_markdown_heading():
    doc = parse("題\n著\n\n序章［＃「序章」は大見出し］\n")
    md = doc.to_markdown()
    assert md.startswith("# 序章")


def test_to_markdown_bold():
    doc = parse("題\n著\n\n重要［＃「重要」は太字］\n")
    assert "**重要**" in doc.to_markdown()


def test_to_markdown_image():
    doc = parse("題\n著\n\n［＃挿絵（fig1.png、横40×縦50）入る］\n")
    assert "![挿絵](fig1.png)" in doc.to_markdown()


def test_to_markdown_bouten():
    # 傍点・傍線は mdit-py-cjk-friendly の bouten 記法 [対象]{.class} に
    doc = parse("題\n著\n\n邪智暴虐［＃「邪智暴虐」に傍点］\n")
    assert "[邪智暴虐]{.sesame_dot}" in doc.to_markdown()
    doc2 = parse("題\n著\n\nあ［＃「あ」に二重傍線］\n")
    assert "[あ]{.underline_double}" in doc2.to_markdown()


def test_bouten_roundtrip_through_washi():
    """注記 → Markdown → washi-md(bouten プラグイン) → <em class> の往復。"""
    doc = parse("題\n著\n\n邪智暴虐［＃「邪智暴虐」に傍点］の王。\n")
    html = washi_md.render(doc.to_markdown(), vertical=True)
    assert '<em class="sesame_dot">邪智暴虐</em>' in html
    # washi の CSS に text-emphasis 定義が入っていること（縦書きで圏点が出る）
    assert "text-emphasis" in html


def test_to_washi_html_vertical():
    # 縦書きHTMLが生成される（washi-mdは純Python・オフライン）
    doc = parse("題\n著\n\n本文です。{漢字|かんじ}\n".replace("{漢字|かんじ}", ""))
    html = doc.to_washi_html(vertical=True)
    assert isinstance(html, str) and len(html) > 200
    # ルビがwashi側で<ruby>に展開される
    doc2 = parse("題\n著\n\n漢字《かんじ》。\n")
    assert "<ruby>" in doc2.to_washi_html(vertical=True)
