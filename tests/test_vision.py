"""vision.py（底本ページ写真→注記テキスト）のテスト。偽サーバでオフライン検証。"""
import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from pybunko.vision import (ClaudeVisionEngine, OpenAiVisionEngine,
                            TRANSCRIBE_PROMPT, _media_type, transcribe_pages)
from pybunko.ai import ClaudeClient

PNG1PX = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk'
    '+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==')


def _serve(handler_cls):
    srv = HTTPServer(('127.0.0.1', 0), handler_cls)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


@pytest.fixture
def fake_openai():
    received: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            assert self.path == '/v1/chat/completions'
            received.append(json.loads(
                self.rfile.read(int(self.headers['content-length']))))
            data = json.dumps({'choices': [{'message': {
                'content': '　メロスは激怒した。\n'}}]}).encode()
            self.send_response(200)
            self.send_header('content-type', 'application/json')
            self.send_header('content-length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            pass

    srv = _serve(Handler)
    yield f'http://127.0.0.1:{srv.server_port}/v1', received
    srv.shutdown()


def test_openai_vision_roundtrip(fake_openai):
    base, received = fake_openai
    eng = OpenAiVisionEngine(base_url=base, model='qwen-vl')
    text = transcribe_pages([('p1.png', PNG1PX), ('p2.jpg', PNG1PX)], eng)
    # ページごとに書き起こし、空行1つで結合
    assert text == '　メロスは激怒した。\n\n　メロスは激怒した。\n'
    assert len(received) == 2
    req = received[0]
    assert req['model'] == 'qwen-vl'
    blocks = req['messages'][0]['content']
    assert blocks[0]['text'] == TRANSCRIBE_PROMPT
    assert '底本どおりに写す' in blocks[0]['text']
    # 1枚目はpng、2枚目はjpegのdata URL
    assert blocks[1]['image_url']['url'].startswith('data:image/png;base64,')
    b64 = received[1]['messages'][0]['content'][1]['image_url']['url']
    assert b64.startswith('data:image/jpeg;base64,')
    assert base64.b64decode(b64.split(',', 1)[1]) == PNG1PX


@pytest.fixture
def fake_claude():
    received: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            assert self.path == '/v1/messages'
            received.append(json.loads(
                self.rfile.read(int(self.headers['content-length']))))
            data = json.dumps({'content': [
                {'type': 'text', 'text': '　メロスは激怒した。'}]}).encode()
            self.send_response(200)
            self.send_header('content-type', 'application/json')
            self.send_header('content-length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            pass

    srv = _serve(Handler)
    yield f'http://127.0.0.1:{srv.server_port}', received
    srv.shutdown()


def test_claude_vision_image_blocks(fake_claude):
    base, received = fake_claude
    eng = ClaudeVisionEngine(ClaudeClient(api_key='k', base_url=base))
    out = eng.transcribe(PNG1PX, 'image/png')
    assert out == '　メロスは激怒した。\n'
    content = received[0]['messages'][0]['content']
    assert content[0]['type'] == 'image'
    assert content[0]['source']['media_type'] == 'image/png'
    assert base64.b64decode(content[0]['source']['data']) == PNG1PX
    assert content[1]['type'] == 'text'
    assert received[0]['system'] == TRANSCRIBE_PROMPT


def test_media_type():
    assert _media_type('IMG_0001.JPG') == 'image/jpeg'
    assert _media_type('page.png') == 'image/png'
    assert _media_type('page.webp') == 'image/webp'
    assert _media_type('noext') == 'image/jpeg'


def test_progress_callback(fake_openai):
    base, _ = fake_openai
    seen = []
    transcribe_pages([('a.jpg', PNG1PX)], OpenAiVisionEngine(base_url=base),
                     progress=lambda d, t: seen.append((d, t)))
    assert seen == [(1, 1)]
