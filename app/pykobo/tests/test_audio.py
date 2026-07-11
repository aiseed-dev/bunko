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


def test_openai_speech_engine_against_fake_server(tmp_path):
    """OpenAI互換 /v1/audio/speech（MS-S1 MAX等のローカルTTSサーバ想定）に
    正しいリクエストを送り、返った音声を保存できる。偽サーバで検証。"""
    import http.server
    import threading

    from pybunko.audio import OpenAiSpeechEngine

    # 0.2秒の無音WAVを「サーバの返答」として用意
    wav = tmp_path / "resp.wav"
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi',
                    '-i', 'anullsrc=r=24000:cl=mono', '-t', '0.2', str(wav)],
                   check=True)
    payload = wav.read_bytes()
    seen = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            import json as _json
            body = self.rfile.read(int(self.headers['Content-Length']))
            seen['path'] = self.path
            seen['body'] = _json.loads(body)
            seen['auth'] = self.headers.get('Authorization')
            self.send_response(200)
            self.send_header('Content-Type', 'audio/wav')
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        base = f'http://127.0.0.1:{srv.server_port}/v1'
        eng = OpenAiSpeechEngine(base, voice='jf_alpha', api_key='k')
        out = tmp_path / "out.wav"
        eng.synth('メロスは激怒した。', str(out))
        assert out.read_bytes() == payload
        assert seen['path'] == '/v1/audio/speech'
        assert seen['body']['input'] == 'メロスは激怒した。'
        assert seen['body']['voice'] == 'jf_alpha'
        assert seen['auth'] == 'Bearer k'
    finally:
        srv.shutdown()


def test_sbv2_engine_against_fake_server(tmp_path):
    """Style-Bert-VITS2 の /voice（GET・クエリパラメータ）に正しく接続できる。"""
    import http.server
    import threading
    import urllib.parse

    from pybunko.audio import StyleBertVits2Engine

    wav = tmp_path / "resp.wav"
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi',
                    '-i', 'anullsrc=r=24000:cl=mono', '-t', '0.2', str(wav)],
                   check=True)
    payload = wav.read_bytes()
    seen = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            seen['path'] = u.path
            seen['q'] = dict(urllib.parse.parse_qsl(u.query))
            self.send_response(200)
            self.send_header('Content-Type', 'audio/wav')
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        eng = StyleBertVits2Engine(f'http://127.0.0.1:{srv.server_port}',
                                   model='jvnv-F1-jp', style='Neutral',
                                   length=1.1)
        out = tmp_path / "out.wav"
        eng.synth('メロスは激怒した。', str(out))
        assert out.read_bytes() == payload
        assert seen['path'] == '/voice'
        assert seen['q']['text'] == 'メロスは激怒した。'
        assert seen['q']['model_name'] == 'jvnv-F1-jp'
        assert seen['q']['language'] == 'JP'
        assert seen['q']['length'] == '1.1'
        # model_id 数値指定のときは model_id で送る
        eng2 = StyleBertVits2Engine(f'http://127.0.0.1:{srv.server_port}', model=2)
        eng2.synth('あ', str(out))
        assert seen['q']['model_id'] == '2'
    finally:
        srv.shutdown()
