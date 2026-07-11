"""欧文アクセント分解 accent テスト。

aozora2html/test/test_aozora_accent_parser.rb を仕様として翻訳。
Ruby版は use_jisx0213 で `〔&#x00E9;tiquette`（開き括弧を残す挙動）を返すが、
本ライブラリは意味構造ファーストなので、解決できたら**両方の亀甲括弧を外して**
実文字化する（reading/plain/TTSがきれいになる）。Ruby版の期待値はコメントに温存。
"""
from pybunko import accent, parse


def test_etiquette():
    # 〔e'tiquette〕 → étiquette  (e' = U+00E9)
    # Ruby(use_jisx0213): '〔&#x00E9;tiquette'（開き括弧残す）。こちらは括弧を外す。
    assert accent.resolve("〔e'tiquette〕") == "étiquette"


def test_grave_and_circumflex():
    assert accent.resolve("〔a`〕") == "à"      # グレーブ
    assert accent.resolve("〔o^〕") == "ô"      # サーカムフレックス


def test_uppercase():
    assert accent.resolve("〔E'cole〕") == "École"  # E' = U+00C9


def test_ligature_three_level():
    # 3段（リガチャ）: A E & → Æ
    assert accent.resolve("〔AE&〕") == "Æ"


def test_unrecognized_span_kept():
    # アクセントとして分解できない 〔…〕 はそのまま残す
    assert accent.resolve("〔ふつう〕") == "〔ふつう〕"


def test_non_accent_text_untouched():
    assert accent.resolve("これは普通の文。") == "これは普通の文。"


def test_parser_integration():
    doc = parse("題\n著\n\n語源は〔e'tiquette〕である。\n")
    plain = doc.paragraphs[0].plain
    assert "étiquette" in plain
    assert "〔" not in plain and "e'" not in plain
