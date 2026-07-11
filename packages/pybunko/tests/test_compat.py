"""公式互換HTML to_html(compat='aozora') テスト。

aozora2html の Midashi Tag 期待値に構造を合わせる兄弟実装:
    <h5 class="ko-midashi"><a class="midashi_anchor" id="midashiN">…</a></h5>
見出しIDは MidashiCounter（大+100 / 中+10 / 小+1）で採番する。
"""
from pybunko import parse


def test_compat_komidashi_structure():
    # 小見出し → h5 / ko-midashi / midashi_anchor（counter: 小=+1 → midashi1）
    doc = parse("題\n著\n\nテスト見出し［＃「テスト見出し」は小見出し］\n")
    html = doc.to_html(compat='aozora')
    assert ('<h5 class="ko-midashi"><a class="midashi_anchor" '
            'id="midashi1">テスト見出し</a></h5>') in html


def test_compat_omidashi_counter():
    # 大見出し → h3 / o-midashi、counter: 大=+100 → midashi100
    doc = parse("題\n著\n\n序［＃「序」は大見出し］\n")
    html = doc.to_html(compat='aozora')
    assert '<h3 class="o-midashi"><a class="midashi_anchor" id="midashi100">序</a></h3>' in html


def test_compat_counter_accumulates():
    # 大(+100)=100 → 小(+1)=101 のように加算される
    doc = parse("題\n著\n\n大［＃「大」は大見出し］\n小［＃「小」は小見出し］\n")
    html = doc.to_html(compat='aozora')
    assert 'id="midashi100">大' in html
    assert 'id="midashi101">小' in html


def test_default_vs_compat_tag_differs():
    doc = parse("題\n著\n\nA［＃「A」は小見出し］\n")
    assert '<h4 class="ko-midashi">A</h4>' in doc.to_html()            # 意味構造(h4, アンカー無)
    assert '<h5 class="ko-midashi"><a class="midashi_anchor"' in doc.to_html(compat='aozora')


def test_mado_dogyo_classes_compat():
    doc = parse("題\n著\n\n窓［＃「窓」は窓中見出し］\n")
    html = doc.to_html(compat='aozora')
    assert '<h4 class="mado-naka-midashi"><a class="midashi_anchor"' in html
