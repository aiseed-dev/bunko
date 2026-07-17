"""vision.py — 底本ページの写真 → 青空文庫注記テキストの書き起こし。

入力工程（作業マニュアル【入力編】）の「OCR＋人手修正」を、視覚言語モデル
（VLM）で置き換える入口。スマフォのカメラで底本を撮り、工房（Web）へ
アップロード → 書き起こし → 機械チェック（kosei）→ Claude校正、と繋がる。

エンジンは2系統（audio.py の TTS エンジン群と同じ流儀・stdlibのみ）:

  - OpenAiVisionEngine …… OpenAI互換 /v1/chat/completions（画像対応）。
    重作業ノード（Ryzen AI Max+ 級のローカルAIマシン、DESIGN §6.15）で
    llama.cpp / LM Studio / vLLM に載せた**OSSのVLM**（Qwen-VL等）を叩く。
    OSSモデル・ローカル実行が正道（AI方針）。
  - ClaudeVisionEngine …… Claude の画像入力。ローカルノードが無いときの手段。

書き起こしは「底本どおり・推測で埋めない」が絶対規則。VLMの出力は下書きで
あり、必ず人間が底本と突き合わせる（マニュアルの入力者校正に相当）。
"""
from __future__ import annotations

import base64
import json
import os
import urllib.request

from .ai import ClaudeClient

# 入力編マニュアルの要点を蒸留した書き起こし指示。
TRANSCRIBE_PROMPT = """\
あなたは青空文庫の入力者。写真に写った底本のページを、青空文庫注記形式の
プレーンテキストに書き起こす。

守ること（青空文庫作業マニュアル【入力編】より）:
- 底本どおりに写す。誤植と思われてもそのまま（勝手に直さない）。
  旧字・旧かなもそのまま。
- 縦書きは読み順（右の列から左の列へ）。底本の改行位置ではなく、
  段落の切れ目で改行する（1段落=1行）。
- 段落の頭の字下げは全角空白1つ。ただし行頭が「『（などの括弧なら
  字下げしない。
- ルビは親文字の直後に《》で: 学校《がっこう》。ルビのかかり始めが
  漢字の並びの途中なら、その前に｜を置く: 武州｜青梅《おうめ》。
- 傍点は ［＃「対象」に傍点］、見出しは ［＃「○○」は大見出し］
  （レベルは大見出し・中見出し・小見出し）の形式で。
- 判読できない文字は ※［＃判読不可］ と書き、推測で埋めない。
- ページ番号・柱（ページ上下の書名など）・ノンブルは写さない。
- 出力は書き起こしテキストのみ。説明・前置き・コードブロックは不要。"""


def _tidy(text: str) -> str:
    """前後の空行と行末空白を剥がす。行頭の全角空白（字下げ）は保つ。"""
    lines = [ln.rstrip() for ln in text.replace('\r\n', '\n').split('\n')]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return '\n'.join(lines) + '\n'


def _media_type(name: str) -> str:
    n = name.lower()
    if n.endswith('.png'):
        return 'image/png'
    if n.endswith('.webp'):
        return 'image/webp'
    if n.endswith(('.jpg', '.jpeg')):
        return 'image/jpeg'
    return 'image/jpeg'


class OpenAiVisionEngine:
    """OpenAI互換 chat/completions の画像入力で書き起こす（ローカルVLM用）。

    base_url は互換サーバの /v1 まで（例: http://<node>:1234/v1 = LM Studio、
    http://<node>:8080/v1 = llama.cpp server）。AOZORA_VISION_BASE_URL /
    AOZORA_VISION_MODEL 環境変数でも指定できる。
    """
    name = 'openai-vision'

    def __init__(self, base_url: str | None = None, model: str | None = None,
                 api_key: str = ''):
        self.base_url = (base_url or os.environ.get('AOZORA_VISION_BASE_URL')
                         or 'http://127.0.0.1:1234/v1').rstrip('/')
        self.model = model or os.environ.get('AOZORA_VISION_MODEL', 'default')
        self.api_key = api_key

    def transcribe(self, image: bytes, media_type: str = 'image/jpeg',
                   timeout: int = 600) -> str:
        b64 = base64.b64encode(image).decode('ascii')
        body = {
            'model': self.model,
            'max_tokens': 4000,
            'messages': [{'role': 'user', 'content': [
                {'type': 'text', 'text': TRANSCRIBE_PROMPT},
                {'type': 'image_url',
                 'image_url': {'url': f'data:{media_type};base64,{b64}'}},
            ]}],
        }
        headers = {'content-type': 'application/json'}
        if self.api_key:
            headers['authorization'] = f'Bearer {self.api_key}'
        req = urllib.request.Request(
            f'{self.base_url}/chat/completions',
            data=json.dumps(body).encode('utf-8'), headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode('utf-8'))
        return _tidy(data['choices'][0]['message']['content'])


class ClaudeVisionEngine:
    """Claude の画像入力で書き起こす（ローカルノードが無いときの手段）。"""
    name = 'claude-vision'

    def __init__(self, client: ClaudeClient | None = None):
        self.client = client or ClaudeClient()

    def transcribe(self, image: bytes, media_type: str = 'image/jpeg',
                   timeout: int = 600) -> str:
        b64 = base64.b64encode(image).decode('ascii')
        text = self.client.message(
            'このページを書き起こしてください。',
            system=TRANSCRIBE_PROMPT,
            images=[(media_type, b64)], timeout=timeout)
        return _tidy(text)


def transcribe_pages(images: list[tuple[str, bytes]], engine,
                     progress=None) -> str:
    """複数ページ（(ファイル名, バイト列)）を順に書き起こして結合する。

    ページ境界は空行1つ。progress にコールバックで (done, total) を通知。
    """
    parts: list[str] = []
    for i, (name, data) in enumerate(images):
        parts.append(engine.transcribe(data, _media_type(name)))
        if progress:
            progress(i + 1, len(images))
    return '\n'.join(parts)


# ── CLI ───────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        prog='python -m pybunko.vision',
        description='底本ページの写真 → 青空文庫注記テキスト（VLM書き起こし）')
    ap.add_argument('images', nargs='+', help='ページ写真（読み順）')
    ap.add_argument('-o', '--out', help='出力テキスト（省略時は標準出力）')
    ap.add_argument('--engine', choices=['openai', 'claude'], default='openai')
    ap.add_argument('--base-url', help='OpenAI互換サーバ（…/v1 まで）')
    ap.add_argument('--model', help='モデル名')
    a = ap.parse_args(argv)

    if a.engine == 'claude':
        engine = ClaudeVisionEngine(ClaudeClient(model=a.model))
    else:
        engine = OpenAiVisionEngine(base_url=a.base_url, model=a.model)
    from pathlib import Path
    pages = [(p, Path(p).read_bytes()) for p in a.images]
    text = transcribe_pages(
        pages, engine,
        progress=lambda d, t: print(f'  {d}/{t} ページ', flush=True))
    if a.out:
        Path(a.out).write_text(text, encoding='utf-8')
        print(f'書き出し: {a.out}（機械チェック: python -m pybunko.kosei {a.out}）')
    else:
        print(text, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
