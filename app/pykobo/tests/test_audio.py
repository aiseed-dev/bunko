"""朗読パック生成のテスト。

合成エンジンは偽物（ffmpegで無音を生成）に差し替え、ネットワーク無しで
manifest 組み立て・タイミング累積・Opus結合を検証する。ffmpegが無ければskip。
"""
import json
import shutil
import subprocess

import pytest

from pybunko import parse
from pybunko.audio import build_audiobook, speech_paragraphs

pytestmark = pytest.mark.skipif(
    shutil.which('ffmpeg') is None or shutil.which('ffprobe') is None,
    reason='ffmpeg が無い')


class SilenceEngine:
    """テスト用: 指定長の無音WAVを書く偽エンジン。"""
    name = 'silence'
    ext = 'wav'
    voice = 'none'

    def __init__(self, seconds: float = 0.3):
        self.seconds = seconds

    def synth(self, text: str, out_path: str) -> None:
        subprocess.run(
            ['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi',
             '-i', f'anullsrc=r=24000:cl=mono', '-t', str(self.seconds),
             out_path], check=True)


def test_speech_paragraphs_skips_blank_and_uses_reading():
    doc = parse("題\n著\n\n邪智暴虐《じゃちぼうぎゃく》の王。\n\n※〔ゴミ〕だけ\n")
    targets = speech_paragraphs(doc)
    # 読みテキスト（ルビ採用）になっている
    assert targets[0][1].startswith("じゃちぼうぎゃく")


def test_build_audiobook_manifest(tmp_path):
    doc = parse("題名\n著者\n\n一つ目の段落。\n\n二つ目の段落。\n三つ目。\n")
    base = tmp_path / "book"
    m = build_audiobook(doc, str(base), SilenceEngine(0.3))

    assert (tmp_path / "book.opus").exists()
    saved = json.loads((tmp_path / "book.audiobook.json").read_text(encoding="utf-8"))
    assert saved == m
    assert m['title'] == '題名' and m['engine'] == 'silence'
    assert len(m['paras']) == 3
    # タイミングが累積している（各0.3秒前後）
    assert m['paras'][0]['start'] == 0
    assert m['paras'][1]['start'] == pytest.approx(0.3, abs=0.1)
    assert m['paras'][2]['start'] == pytest.approx(0.6, abs=0.2)
    assert m['total'] == pytest.approx(0.9, abs=0.3)
    # 段落indexが元Documentのindexを指す
    assert [p['i'] for p in m['paras']] == [0, 1, 2]


def test_build_audiobook_limit(tmp_path):
    doc = parse("題\n著\n\n" + "\n".join(f"段落{i}。" for i in range(10)) + "\n")
    m = build_audiobook(doc, str(tmp_path / "b"), SilenceEngine(0.2), limit=4)
    assert len(m['paras']) == 4
