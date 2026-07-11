"""Shift_JIS 注記付きテキスト → Unicode JSON 変換パイプラインのテスト。

同梱の走れメロス（zip）で、read_text / to_json / CLI をオフライン検証する。
"""
import json
import pathlib

from aozorabunko import convert, Document

DATA = pathlib.Path(__file__).parent / "data"
MEROSU = str(DATA / "1567_ruby_4948.zip")


def test_read_text_from_zip():
    # X-JIS(zip) → Unicode 復号
    text = convert.read_text(MEROSU)
    assert text.startswith("走れメロス")
    assert "太宰治" in text[:40]


def test_to_json_string_and_file(tmp_path):
    out = tmp_path / "merosu.json"
    js = convert.to_json(MEROSU, str(out))
    assert out.exists()
    d = json.loads(js)
    assert d['title'] == "走れメロス" and d['author'] == "太宰治"
    # 一次データだけで復元でき、ルビも保持
    assert Document.from_dict(d).to_speech_text()[0] == "メロスは激怒した。"


def test_cli_main(tmp_path):
    from aozorabunko.__main__ import main
    out = tmp_path / "m.json"
    assert main([MEROSU, "-o", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))['title'] == "走れメロス"
