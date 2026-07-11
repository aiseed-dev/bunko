"""ゴールデンファイル比較 ── 生成HTMLが公式ファイルと一致することを検証。

入力（注記付きテキスト）と正解出力（公式XHTML）の両方が、青空文庫リポジトリ
（aozorabunko/aozorabunko）に存在する。この検証可能性こそ pyaozora の核心。
同梱の走れメロス（太宰治・パブリックドメイン）で **バイト単位の一致** を担保する。
"""
import io
import pathlib
import zipfile

from pyaozora import to_official_bytes, to_official_html

GOLDEN = pathlib.Path(__file__).parent / "golden"


def _merosu_text() -> str:
    data = (GOLDEN / "1567_ruby_4948.zip").read_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".txt"))
        return zf.read(name).decode("shift_jis")


def test_merosu_byte_exact():
    """走れメロス: 注記テキスト → 公式XHTML が Shift_JIS バイト列まで完全一致。"""
    ours = to_official_bytes(_merosu_text())
    golden = (GOLDEN / "1567_14913.html").read_bytes()
    assert ours == golden, f"byte mismatch: ours={len(ours)} golden={len(golden)}"


def test_official_ruby_format():
    """ルビは公式流儀 <rb>…<rp>（</rp><rt>…</rt><rp>）</rp>。"""
    html = to_official_html(_merosu_text())
    assert ("<ruby><rb>邪智暴虐</rb><rp>（</rp>"
            "<rt>じゃちぼうぎゃく</rt><rp>）</rp></ruby>") in html


def test_page_skeleton():
    """XHTML1.1 の骨格（DOCTYPE / metadata / main_text / 底本 / 図書カード）。"""
    html = to_official_html(_merosu_text())
    assert html.startswith('<?xml version="1.0" encoding="Shift_JIS"?>')
    assert '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="ja" >' in html
    assert '<h1 class="title">走れメロス</h1>' in html
    assert '<div class="main_text">' in html
    assert '<div class="bibliographical_information">' in html
    assert '<a href="JavaScript:goLibCard();" id="goAZLibCard">●図書カード</a>' in html
