"""ai.py（Claude校正クライアント）のテスト。

audio.py のエンジン群と同じ流儀: localhost に Anthropic Messages API の
偽サーバを立て、リクエストの形と返答の解釈を検証する（オフライン）。
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from pybunko.ai import ClaudeClient, _chunks, _parse_findings, locate, proofread


@pytest.fixture
def fake_api():
    """/v1/messages を受けて、固定の疑い1件を返す偽Anthropicサーバ。"""
    received: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            assert self.path == '/v1/messages'
            body = json.loads(self.rfile.read(int(self.headers['content-length'])))
            body['_headers'] = {'x-api-key': self.headers.get('x-api-key'),
                                'anthropic-version':
                                    self.headers.get('anthropic-version')}
            received.append(body)
            reply = {'content': [{'type': 'text', 'text': json.dumps([{
                'quote': 'その間題は',
                'suspect': '間題',
                'suggestion': '問題',
                'reason': '「問」と「間」のOCR誤読と思われる',
            }], ensure_ascii=False)}]}
            data = json.dumps(reply).encode()
            self.send_response(200)
            self.send_header('content-type', 'application/json')
            self.send_header('content-length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            pass

    srv = HTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{srv.server_port}', received
    srv.shutdown()


def test_proofread_roundtrip(fake_api):
    base, received = fake_api
    client = ClaudeClient(api_key='test-key', base_url=base, model='claude-fable-5')
    text = '冒頭。\nその間題は咋日のことだ。\n結び。\n'
    findings = locate(proofread(text, client), text)
    assert len(findings) == 1
    f = findings[0]
    assert f['suspect'] == '間題' and f['suggestion'] == '問題'
    assert f['line'] == 2 and f['chunk'] == 0
    # リクエストの形: モデル・システムプロンプト・認証ヘッダ
    req = received[0]
    assert req['model'] == 'claude-fable-5'
    assert '原稿（底本）尊重' in req['system']
    assert req['_headers']['x-api-key'] == 'test-key'
    assert req['_headers']['anthropic-version'] == '2023-06-01'


def test_client_requires_key(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    c = ClaudeClient()
    assert not c.available
    with pytest.raises(RuntimeError):
        c.message('x')


def test_chunks_split_on_lines():
    text = '\n'.join(f'{i}段落' + 'あ' * 50 for i in range(10))
    parts = _chunks(text, size=120)
    assert len(parts) > 2
    assert '\n'.join(parts) == text          # 復元可能＝取りこぼし無し


def test_parse_findings_tolerates_prose():
    reply = '以下が疑いです。\n[{"quote": "人問", "suspect": "人問"}]\n以上。'
    assert _parse_findings(reply)[0]['quote'] == '人問'
    assert _parse_findings('疑いはありません。') == []
    assert _parse_findings('[]') == []
