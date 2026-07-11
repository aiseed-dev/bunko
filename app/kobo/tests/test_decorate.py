"""装飾（傍点・傍線・圏点・太字）テスト。

aozora2html/test/test_decorate_tag.rb と yml/command_table.yml を仕様として翻訳。
Ruby版 Decorate.to_s は <span class="foo">テスト</span> 相当の汎用ラッパ。
本ライブラリは意味構造ファーストで、Paragraph.decorations の (対象, class, tag) と
自前レンダラ出力で判定する。
"""
from pybunko import parse, decorate
from pybunko.formats import to_html


def _decos(text):
    return parse(f"題\n著\n\n{text}\n").paragraphs[0].decorations or []


def test_bouten():
    d = _decos("邪智暴虐［＃「邪智暴虐」に傍点］")
    assert d == [("邪智暴虐", "sesame_dot", "em")]


def test_bouten_variants():
    assert _decos("あ［＃「あ」に丸傍点］")[0][1] == "black_circle"
    assert _decos("あ［＃「あ」に二重丸傍点］")[0][1] == "bullseye"
    assert _decos("あ［＃「あ」に蛇の目傍点］")[0][1] == "fisheye"
    assert _decos("あ［＃「あ」にばつ傍点］")[0][1] == "saltire"


def test_underlines():
    assert _decos("あ［＃「あ」に傍線］")[0][1] == "underline_solid"
    assert _decos("あ［＃「あ」に二重傍線］")[0][1] == "underline_double"
    assert _decos("あ［＃「あ」に鎖線］")[0][1] == "underline_dotted"
    assert _decos("あ［＃「あ」に破線］")[0][1] == "underline_dashed"
    assert _decos("あ［＃「あ」に波線］")[0][1] == "underline_wave"


def test_futoji_shatai():
    d = _decos("重要［＃「重要」は太字］")
    assert d == [("重要", "futoji", "span")]
    assert _decos("斜め［＃「斜め」は斜体］")[0] == ("斜め", "shatai", "span")


def test_direction_filter():
    # 左に傍点 → 反対側 sesame_dot_after
    assert _decos("あ［＃「あ」の左に傍点］")[0][1] == "sesame_dot_after"
    # 上に傍線 → 上線化（under→over）
    assert _decos("あ［＃「あ」の上に傍線］")[0][1] == "overline_solid"


def test_deco_class_helper():
    # command_table.yml 準拠（Ruby: ['sesame_dot', 'em']）
    assert decorate.deco_class("傍点") == ("sesame_dot", "em")
    assert decorate.deco_class("太字") == ("futoji", "span")
    assert decorate.deco_class("傍点", "下") == ("sesame_dot_after", "em")


def test_emphasis_compat_property():
    # 後方互換プロパティ: 傍点対象のみを返す
    p = parse("題\n著\n\n強調［＃「強調」に傍点］\n").paragraphs[0]
    assert p.emphasis == ["強調"]


def test_to_html_bouten():
    html = to_html(parse("題\n著\n\n語［＃「語」に傍点］\n"))
    assert '<em class="sesame_dot">語</em>' in html


def test_to_html_futoji():
    html = to_html(parse("題\n著\n\n太［＃「太」は太字］\n"))
    assert '<span class="futoji">太</span>' in html
