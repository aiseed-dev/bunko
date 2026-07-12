"""改ページ類・訂正/ママ注記・後置形地付きのテスト（一括点検で選んだ上位注記）。

2026-07-12 の国勢調査（400作品）で出現作品数の多かった未対応注記:
訂正49作品・ママ30作品・地からN字上げ後置形23作品・改ページ14作品。
本文は保ち、情報を Document（pb / notes）に構造で残す。
"""
from pybunko import Document, parse


def _parse(body: str, unknown=None):
    return parse(f'題\n著\n\n{body}\n', unknown_notes=unknown)


def test_page_breaks():
    u = []
    doc = _parse('前。\n［＃改ページ］\n後。\n［＃改丁］\n［＃改段］\n'
                 '［＃ページの左右中央］\n中央の章名。', u)
    assert u == []
    pbs = [p.page_break for p in doc.paragraphs]
    assert pbs == [None, 'page', None, 'sheet', 'column', 'center', None]
    # マーカー段落は本文を持たない
    assert doc.paragraphs[1].plain == ''


def test_teisei_and_mama():
    u = []
    doc = _parse('モーニングだとか紋附だとか［＃「紋附だとか」は底本では「絞附だとか」］した。\n'
                 '広場へに［＃「広場へに」はママ］店でも。', u)
    assert u == []
    p1, p2 = doc.paragraphs
    # 本文は訂正後の形のまま（勝手に戻さない）・注記は構造で残る
    assert p1.plain == 'モーニングだとか紋附だとかした。'
    assert p1.notes == [{'t': '紋附だとか', 'kind': 'teisei', 'src': '絞附だとか'}]
    assert p2.notes == [{'t': '広場へに', 'kind': 'mama'}]


def test_ruby_teisei_and_chuki():
    u = []
    doc = _parse('私は籠《ざる》［＃ルビの「ざる」は底本では「さる」］をさげ\n'
                 '吹喋［＃「喋」に「ママ」の注記］\n'
                 '豊饒［＃「豊饒」の左に「ニギハヒ」の注記］', u)
    assert u == []
    n1, n2, n3 = (p.notes[0] for p in doc.paragraphs)
    assert n1 == {'t': 'ざる', 'kind': 'ruby_teisei', 'src': 'さる'}
    assert n2 == {'t': '喋', 'kind': 'chuki', 'note': 'ママ'}
    assert n3 == {'t': '豊饒', 'kind': 'chuki_left', 'note': 'ニギハヒ'}
    # ルビ自体は生きている
    assert doc.paragraphs[0].segments[1] == ('籠', 'ざる')


def test_inline_chitsuki_splits_line():
    # 「凶」（芥川）の実例: 行の途中から地に寄せる後置形
    u = []
    doc = _parse('（大正十五年四月十三日浄書）［＃地から１字上げ］〔遺稿〕', u)
    assert u == []
    p1, p2 = doc.paragraphs
    assert p1.plain == '（大正十五年四月十三日浄書）' and p1.align is None
    assert p2.plain == '〔遺稿〕' and p2.align == 'right' and p2.align_offset == 1


def test_json_roundtrip_with_pb_and_notes():
    doc = _parse('前。\n［＃改ページ］\n吹喋［＃「喋」に「ママ」の注記］')
    d = doc.to_dict()
    assert d['paragraphs'][1]['pb'] == 'page'
    assert d['paragraphs'][2]['notes'][0]['kind'] == 'chuki'
    assert Document.from_dict(d).to_dict() == d
