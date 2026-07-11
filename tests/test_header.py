"""見出し header/midashi テスト。

aozora2html/test/test_midashi_tag.rb を「仕様書」として翻訳。
Ruby版は Tag.to_s の厳密HTML（<h5 class="ko-midashi"><a class="midashi_anchor"...>）
を検査するが、本ライブラリは意味構造ファーストなので heading_level / heading_type と、
自前レンダラの class 名で判定する。厳密なアンカー付きHTMLは将来の compat レンダラで。

見出しの3形式（後置・単一行ブロック・複数行ブロック）と、種別（normal/同行/窓）を網羅する。
"""
from aozorabunko import parse
from aozorabunko.formats import midashi_class, to_html


def _headings(doc):
    return [p for p in doc.paragraphs if p.heading_level]


def test_inline_omidashi():
    # 後置形式・大見出し（normal）
    doc = parse("題\n著\n\n序章［＃「序章」は大見出し］\n")
    h = _headings(doc)[0]
    assert h.heading_level == 2 and h.heading_type == "normal"
    assert h.plain == "序章"


def test_inline_mado_nakamidashi():
    # 窓中見出し
    doc = parse("題\n著\n\n第一［＃「第一」は窓中見出し］\n")
    h = _headings(doc)[0]
    assert h.heading_level == 3 and h.heading_type == "mado"


def test_inline_dogyo_komidashi():
    # 同行小見出し
    doc = parse("題\n著\n\nはじめに［＃「はじめに」は同行小見出し］\n")
    h = _headings(doc)[0]
    assert h.heading_level == 4 and h.heading_type == "dogyo"


def test_block_single_line():
    # 単一行ブロック  ［＃大見出し］序章［＃大見出し終わり］
    doc = parse("題\n著\n\n［＃大見出し］序章［＃大見出し終わり］\n")
    h = _headings(doc)[0]
    assert h.heading_level == 2 and h.heading_type == "normal"
    assert h.plain == "序章"


def test_block_multiline():
    # 複数行ブロック（開始行と終了行の間を1見出しにまとめる）
    doc = parse("題\n著\n\n［＃中見出し］\n上の巻\nその一\n［＃中見出し終わり］\n")
    hs = _headings(doc)
    assert len(hs) == 1
    assert hs[0].heading_level == 3
    assert hs[0].plain == "上の巻その一"


def test_midashi_class_names():
    # aozora2html互換のクラス名（Ruby: ko-midashi / mado-ko-midashi）
    assert midashi_class(2, "normal") == "o-midashi"
    assert midashi_class(3, "normal") == "naka-midashi"
    assert midashi_class(4, "normal") == "ko-midashi"
    assert midashi_class(4, "mado") == "mado-ko-midashi"
    assert midashi_class(3, "dogyo") == "dogyo-naka-midashi"


def test_to_html_heading():
    doc = parse("題\n著\n\n序章［＃「序章」は大見出し］\n")
    html = to_html(doc)
    # 意味構造レンダラの出力（compatではない）: <h2 class="o-midashi">序章</h2>
    assert '<h2 class="o-midashi">序章</h2>' in html


def test_body_paragraph_not_heading():
    # 通常段落は heading_level 0
    doc = parse("題\n著\n\nこれは本文です。\n")
    assert doc.paragraphs[0].heading_level == 0
