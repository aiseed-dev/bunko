"""字下げ・地付き・字詰め（レイアウト系, HANDOFF「dir系」）テスト。

aozora2html の Jisage/Chitsuki/Jizume タグ（margin-left / text-align:right / width）を
意味構造ファーストで移植。判定は Paragraph のレイアウト属性と自前レンダラの class/style。
Ruby版 to_s の厳密HTML（<div class="jizume_50" style="width: 50em">）はコメントに温存。
"""
from aozorabunko import parse
from aozorabunko.formats import to_html
from aozorabunko.parser import _jp_number


def _body(text):
    return parse(f"題\n著\n\n{text}\n").paragraphs


def test_jp_number():
    assert _jp_number("3") == 3
    assert _jp_number("１０") == 10
    assert _jp_number("三") == 3
    assert _jp_number("二十") == 20
    assert _jp_number("二十三") == 23


def test_single_line_jisage():
    p = _body("［＃３字下げ］本文です。")[0]
    assert p.indent == 3
    assert p.plain == "本文です。"


def test_kanji_jisage():
    p = _body("［＃三字下げ］漢数字。")[0]
    assert p.indent == 3


def test_block_jisage():
    ps = parse("題\n著\n\n［＃ここから２字下げ］\n一行目\n二行目\n"
               "［＃ここで字下げ終わり］\n地の文\n").paragraphs
    inside = [p for p in ps if p.plain in ("一行目", "二行目")]
    assert all(p.indent == 2 for p in inside)
    outside = [p for p in ps if p.plain == "地の文"][0]
    assert outside.indent == 0  # ブロックを抜けたら字下げ解除


def test_chitsuki():
    # 地付き → 右寄せ
    p = _body("［＃地付き］署名")[0]
    assert p.align == "right"
    assert p.plain == "署名"


def test_jiage():
    # 地から２字上げ → 右寄せ＋右マージン2
    p = _body("［＃地から２字上げ］署名")[0]
    assert p.align == "right" and p.align_offset == 2


def test_block_jizume():
    ps = parse("題\n著\n\n［＃ここから２０字詰め］\n詰めた行\n"
               "［＃ここで字詰め終わり］\n").paragraphs
    inside = [p for p in ps if p.plain == "詰めた行"][0]
    assert inside.jizume == 20


def test_to_html_jisage():
    html = to_html(parse("題\n著\n\n［＃３字下げ］本文\n"))
    # 意味構造レンダラ: <p class="jisage_3" style="margin-left: 3em">本文</p>
    assert 'class="jisage_3"' in html
    assert 'margin-left: 3em' in html


def test_to_html_chitsuki():
    html = to_html(parse("題\n著\n\n［＃地付き］署名\n"))
    assert 'text-align: right' in html


def test_normal_paragraph_no_layout():
    p = _body("ふつうの段落。")[0]
    assert p.indent == 0 and p.align is None and p.jizume == 0
