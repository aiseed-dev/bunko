"""外字 gaiji 解決テスト。

aozora2html/test/test_gaiji_tag.rb を「仕様書」として翻訳したもの。
本ライブラリは意味構造ファーストなので、判定は Ruby版 EmbedGaiji の
`<img>` / `&#xXXXX;` HTML ではなく、**解決後の実Unicode文字**（Document.plain に入る）
に対して行う。Ruby版の期待HTMLは各テストのコメントに温存し、将来の
compat レンダラ（to_html(compat='aozora')）の受け入れ基準とする。
"""
from aozorabunko import gaiji, parse


def test_lookup_snowman():
    # Ruby: EmbedGaiji(... '1-06-75' ..., use_jisx0213:true).to_s == '&#x2603;'
    #   → 面区点 1-06-75 は雪だるま ☃ (U+2603)
    assert gaiji.lookup_menkuten(1, 6, 75) == "☃"


def test_menkuten_zero_padding():
    # 1-85-1 のような非ゼロ詰め表記も %1d-%02d-%02d に正規化して引ける
    assert gaiji.lookup_menkuten(1, 85, 1) is not None
    assert gaiji.lookup_menkuten("1", "85", "1") == gaiji.lookup_menkuten(1, 85, 1)


def test_resolve_note_body_menkuten():
    # 注記の中身から面区点を解決（第N水準ラベルは面区点の面と混同しない）
    assert gaiji.resolve_note_body("「雪だるま」、第1水準1-06-75") == "☃"
    assert gaiji.resolve_note_body("「木＋若」、第3水準1-85-1") == gaiji.lookup_menkuten(1, 85, 1)


def test_resolve_note_body_unicode_direct():
    # U+XXXX 直接指定（新しい記法）。U+9AD9 = 髙
    assert gaiji.resolve_note_body("「はしごだか」、U+9AD9") == "髙"


def test_combining_sequence_preserved():
    # 合成列 か゚ (1-04-87 = か + 半濁点) は2文字として保持される
    assert gaiji.lookup_menkuten(1, 4, 87) == "か゚"
    assert len(gaiji.lookup_menkuten(1, 4, 87)) == 2


def test_resolve_in_running_text():
    # 本文中の外字注記まるごとが実文字に置換される（※ も注記も残らない）
    text = "彼は※［＃「雪だるま」、第1水準1-06-75］を見た。"
    assert gaiji.resolve(text) == "彼は☃を見た。"


def test_non0213_falls_back_to_geta():
    # 非0213外字（合成説明のみで対応文字なし）は 〓 に。本文から欠落させない。
    assert gaiji.resolve("※［＃「(木＋若)の異体字」、非0213外字］") == gaiji.GETA


def test_unknown_menkuten_falls_back_to_geta():
    # 表に無い面区点も 〓（存在しないキーで安全側に倒す）
    assert gaiji.resolve("※［＃「架空」、第4水準2-99-99］") == gaiji.GETA


def test_parser_integration_gaiji_not_dropped():
    # parse() 経由で Document.plain に解決済み文字が入り、外字が欠落しない。
    # （従来は ［＃…］ 一括除去で外字が消え、裸の ※ が残っていた）
    doc = parse("題\n著\n\n序に※［＃「雪だるま」、第1水準1-06-75］が降る。\n")
    plain = doc.paragraphs[0].plain
    assert "☃" in plain
    assert "※" not in plain
    assert "［＃" not in plain
