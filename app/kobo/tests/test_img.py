"""挿絵 img テスト。

aozora2html/test/test_img_tag.rb と driver の PAT_IMAGE を仕様として翻訳。
Ruby版 Img.to_s は <img class="img1" width=.. height=.. src=.. alt=.. />。
本ライブラリは意味構造ファーストで、Paragraph.image (src, w, h, caption) と
自前レンダラの <img class="illustration"> で判定する。挿絵はミラーの files/ 基準で解決。
"""
from pybunko import parse
from pybunko.formats import to_html


def test_img_with_dimensions():
    doc = parse("題\n著\n\n［＃挿絵（fig42630_01.png、横520×縦354）入る］\n")
    p = doc.paragraphs[0]
    assert p.image == ("fig42630_01.png", 520, 354, "挿絵")
    assert p.plain == ""  # 挿絵注記だけの段落は本文テキスト空


def test_img_without_dimensions():
    doc = parse("題\n著\n\n［＃（fig001.png）入る］\n")
    src, w, h, cap = doc.paragraphs[0].image
    assert src == "fig001.png" and w is None and h is None


def test_image_base_resolution():
    # ミラーのfiles/ディレクトリを基準にsrcを解決
    base = ("https://raw.githubusercontent.com/aozorabunko/aozorabunko/"
            "master/cards/000035/files/")
    doc = parse("題\n著\n\n［＃挿絵（fig1_2.png、横40×縦50）入る］\n", image_base=base)
    assert doc.paragraphs[0].image[0] == base + "fig1_2.png"


def test_to_html_img():
    doc = parse("題\n著\n\n［＃挿絵（fig9.png、横40×縦50）入る］\n")
    html = to_html(doc)
    # 意味構造レンダラ: <img class="illustration" src="fig9.png" width="40" height="50" alt="挿絵" />
    assert 'class="illustration"' in html
    assert 'src="fig9.png"' in html
    assert 'width="40"' in html and 'height="50"' in html


def test_non_image_note_untouched():
    # 挿絵以外の注記は image を作らない
    doc = parse("題\n著\n\nふつうの段落。\n")
    assert doc.paragraphs[0].image is None
