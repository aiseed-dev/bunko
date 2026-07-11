"""回帰テスト ── 走れメロスで全経路が落ちないことを固定する。

新しい注記対応を足すたびに、この作品でパース・変換が壊れないことを保証する。
すべて同梱キャッシュから読むためオフラインで完結する（conftest が urlopen を遮断）。
"""


def test_text_offline(merosu_work):
    """本文（注記付きテキスト）が同梱キャッシュから読める。"""
    text = merosu_work.text()
    assert text.startswith("走れメロス")
    assert "太宰治" in text[:50]


def test_document_structure(merosu_doc):
    """Document の書誌と段落数。"""
    assert merosu_doc.title == "走れメロス"
    assert merosu_doc.author == "太宰治"
    # 長さは版に依存しうるので下限で固定（現状75段落）
    assert len(merosu_doc.paragraphs) >= 70


def test_to_html_has_ruby(merosu_doc):
    """HTML化でルビが <ruby> として出る。"""
    html = merosu_doc.to_html()
    assert "<ruby>" in html
    # 邪智暴虐《じゃちぼうぎゃく》のルビが読みとして出ている
    assert "<rt>" in html


def test_to_speech_text(merosu_doc):
    """読み上げ文リスト。冒頭の一文が取れる。"""
    sents = merosu_doc.to_speech_text()
    assert sents[0] == "メロスは激怒した。"
    assert len(sents) > 100


def test_reading_uses_ruby(merosu_doc):
    """reading はルビを読みとして採用する（TTS誤読対策の要）。"""
    # どこかの段落に、plain と reading が異なる（ルビ採用された）箇所がある
    assert any(p.plain != p.reading for p in merosu_doc.paragraphs)


def test_to_epub(merosu_doc, tmp_path):
    """EPUB が書き出せてファイルになる。"""
    out = tmp_path / "merosu.epub"
    merosu_doc.to_epub(str(out))
    assert out.exists() and out.stat().st_size > 0


def test_json_roundtrip(merosu_doc):
    """Unicode一次データ（JSON）だけで Document を完全復元でき、同じ出力になる。"""
    import json
    from aozorabunko import Document
    d = json.loads(merosu_doc.to_json())
    assert d['title'] == '走れメロス' and d['author'] == '太宰治'
    assert d['paragraphs'][0]['seg']              # セグメントが入っている
    # 往復: JSON → Document → 同じHTML・同じ読み上げ
    back = Document.from_dict(d)
    assert back.to_html() == merosu_doc.to_html()
    assert back.to_speech_text() == merosu_doc.to_speech_text()
    # ルビは読みデータとして保持される
    assert any('r' in s for p in d['paragraphs'] for s in p['seg'])


def test_unknown_notes_collector():
    """unknown_notes=list で、解釈できず除去した注記を収集できる（工作員ツール用）。"""
    from aozorabunko import parse
    notes = []
    parse("題\n著\n\n本文［＃ページの左右中央］と［＃「行右小書き」は解釈される］続き"
          "［＃改丁］。\n", unknown_notes=notes)
    assert "ページの左右中央" in notes
    assert "改丁" in notes
    # 対応済みの注記（見出し・字下げ・傍点等）は混ざらない
    notes2 = []
    parse("題\n著\n\n［＃３字下げ］序［＃「序」は大見出し］\n", unknown_notes=notes2)
    assert notes2 == []


def test_keep_blank_lines():
    """keep_blank_lines=True で空行が空段落として保持される（pyaozora向け）。"""
    from aozorabunko import parse
    src = "題\n著\n一行目\n\n\n二行目\n"
    # 既定は空行を捨てる
    assert [p.plain for p in parse(src).paragraphs] == ["一行目", "二行目"]
    # keep=True: 一行目と二行目の間に空段落（segments==[]）が2つ挟まる
    plains = [p.plain for p in parse(src, keep_blank_lines=True).paragraphs]
    i, j = plains.index("一行目"), plains.index("二行目")
    assert plains[i + 1:j] == ["", ""]
