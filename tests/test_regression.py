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
    from pybunko import Document
    d = json.loads(merosu_doc.to_json())
    assert d['title'] == '走れメロス' and d['author'] == '太宰治'
    assert d['paragraphs'][0]['seg']              # セグメントが入っている
    # 往復: JSON → Document → 同じHTML・同じ読み上げ
    back = Document.from_dict(d)
    assert back.to_html() == merosu_doc.to_html()
    assert back.to_speech_text() == merosu_doc.to_speech_text()
    # ルビは読みデータとして保持される
    assert any('r' in s for p in d['paragraphs'] for s in p['seg'])


def test_license_roundtrips_and_defaults_empty():
    """license は著作権者の選択。未指定なら空文字（既定=作者に著作権あり）。"""
    from pybunko import Document

    doc = Document(title='t', author='a', paragraphs=[])
    assert doc.license == ''
    assert doc.to_dict()['license'] == ''

    licensed = Document(title='t', author='a', paragraphs=[], license='CC BY 4.0')
    d = licensed.to_dict()
    assert d['license'] == 'CC BY 4.0'
    assert Document.from_dict(d).license == 'CC BY 4.0'


def test_unknown_notes_collector():
    """unknown_notes=list で、解釈できず除去した注記を収集できる（工作員ツール用）。"""
    from pybunko import parse
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
    """keep_blank_lines=True で空行が空段落として保持される（official向け）。"""
    from pybunko import parse
    src = "題\n著\n一行目\n\n\n二行目\n"
    # 既定は空行を捨てる
    assert [p.plain for p in parse(src).paragraphs] == ["一行目", "二行目"]
    # keep=True: 一行目と二行目の間に空段落（segments==[]）が2つ挟まる
    plains = [p.plain for p in parse(src, keep_blank_lines=True).paragraphs]
    i, j = plains.index("一行目"), plains.index("二行目")
    assert plains[i + 1:j] == ["", ""]


# ── パーサ回帰: レビュー(2026-07-17)で見つかった2件 ─────────────────────

from pybunko import parser


def test_katakana_and_latin_ruby():
    """｜なしルビはカタカナ・欧文の連なりにも掛かる（吾輩は猫であるに実在）。"""
    d = parser.parse(
        '題\n著\n\nワグネル《わぐねる》先生とLichtenberg《リヒテンベルヒ》の話。\n')
    segs = d.paragraphs[0].segments
    assert ('ワグネル', 'わぐねる') in segs
    assert ('Lichtenberg', 'リヒテンベルヒ') in segs
    assert all('《' not in t for t, _ in segs)


def test_hiragana_and_zenkaku_latin_ruby():
    d = parser.parse('題\n著\n\nそれはｖｉｏｌｉｎ《ヴァイオリン》です。\n')
    assert ('ｖｉｏｌｉｎ', 'ヴァイオリン') in d.paragraphs[0].segments


def test_kanji_ruby_unchanged():
    """従来の漢字ルビは従来どおり（直前の漢字連続だけに掛かる）。"""
    d = parser.parse('題\n著\n\nいまは邪智暴虐《じゃちぼうぎゃく》の王だ。\n')
    assert ('邪智暴虐', 'じゃちぼうぎゃく') in d.paragraphs[0].segments


def test_unclosed_heading_block_does_not_swallow_body():
    """「見出し終わり」の無い複数行見出しでも本文が消えない（以前は全喪失）。"""
    d = parser.parse('題\n著\n\n［＃中見出し］\n上の巻\n以降の本文です。\n続きの行。\n')
    plains = [(p.heading_level, p.plain) for p in d.paragraphs]
    assert (3, '上の巻') in plains          # 最初の行は見出しとして立つ
    assert (0, '以降の本文です。') in plains  # 残りは本文として排出される
    assert (0, '続きの行。') in plains


# ── Medium群の回帰(2026-07-17レビュー) ─────────────────────────────

def test_decoration_applies_to_correct_occurrence():
    """同じ文字が複数回出るとき、注記の直前の出現に装飾が掛かる。"""
    from pybunko.formats import to_html
    d = parser.parse('題\n著\n\n昧爽の空、意味の昧［＃「昧」に傍点］。\n')
    html = to_html(d)
    # 装飾対象は2つ目の「昧」（「意味の昧」側）
    assert html.count('<em class="sesame_dot">昧</em>') == 1
    head = html.split('<em', 1)[0]
    assert '昧爽' in head  # 1つ目の昧（昧爽）は素のまま


def test_decoration_not_injected_into_ruby_reading():
    """ルビ読み(<rt>)の中に同じ文字があっても装飾が入らない。"""
    from pybunko.formats import to_html
    d = parser.parse('題\n著\n\n味《み》と、み［＃「み」に傍点］。\n')
    html = to_html(d)
    assert '<rt>み</rt>' in html            # ルビ読みは無傷
    assert '<em class="sesame_dot">み</em>' in html


def test_decoration_after_ruby_base():
    """装飾対象とその注記の間にルビが挟まっても失われない。"""
    d = parser.parse('題\n著\n\n山月記《さんげつき》［＃「山月記」に傍点］\n')
    deco = d.paragraphs[0].decorations
    assert deco and deco[0][:3] == ('山月記', 'sesame_dot', 'em')
    assert d.paragraphs[0].plain == '山月記'  # ルビ親文字は本文に残る


def test_parse_single_line_no_indexerror():
    d = parser.parse('題名だけ')
    assert d.title == '題名だけ' and d.author == ''


def test_document_roundtrip_with_decoration_occurrence():
    d = parser.parse('題\n著\n\nああ、あ［＃「あ」に傍点］。\n')
    rt = parser.Document.from_dict(d.to_dict())
    assert rt.paragraphs[0].decorations[0] == d.paragraphs[0].decorations[0]


def test_epub_identifier_is_stable():
    from pybunko.formats import to_epub
    import tempfile, os, zipfile, re
    d = parser.parse('題\n著\n\n本文。\n')
    ids = []
    for _ in range(2):
        with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as f:
            path = f.name
        to_epub(d, path)
        with zipfile.ZipFile(path) as z:
            opf = next(n for n in z.namelist() if n.endswith('.opf'))
            m = re.search(r'aozora-[0-9a-f]+', z.read(opf).decode('utf-8'))
            ids.append(m.group(0))
        os.unlink(path)
    assert ids[0] == ids[1]  # プロセス跨ぎでも同一ID


def test_official_bytes_keeps_non_sjis_as_charref():
    from pybunko.official import to_official_bytes
    # 第3水準等の実Unicode文字(挘 U+6318=25368)は Shift_JIS に無い。
    # errors='xmlcharrefreplace' で10進数値文字参照 &#25368; になる
    # （errors='replace' の '?' 無言欠字ではない）。
    b = to_official_bytes('挘る話\n著\n\n本文。\n')
    assert b'&#25368;' in b


def test_db_search_escapes_like_wildcards(tmp_path):
    from pybunko import db
    dbp = str(tmp_path / 'x.db')
    import sqlite3
    con = sqlite3.connect(dbp)
    con.execute("CREATE TABLE works (work_id TEXT, title TEXT, title_yomi TEXT, "
                "author TEXT, author_yomi TEXT, row TEXT, card_url TEXT)")
    con.executemany("INSERT INTO works VALUES (?,?,?,?,?,?,?)", [
        ('1', '100%の恋', '', '甲', '', '', ''),
        ('2', '普通の話', '', '乙', '', '', ''),
    ])
    con.commit(); con.close()
    hits = db.search(dbp, '100%')
    assert [h['title'] for h in hits] == ['100%の恋']  # % がワイルドカードにならない
