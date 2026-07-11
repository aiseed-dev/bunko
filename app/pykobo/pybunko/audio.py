"""audio.py — 朗読パックの事前生成（先に作っておく読み上げ）

端末TTSのリアルタイム合成には弱点がある（環境により声が無い・品質がばらつく）。
そこで工房側で**事前に**朗読音声を合成し、「朗読パック」= 音声1ファイル（Opus）＋
段落タイミング manifest（JSON）として書き出す。アプリは再生してmanifestで
段落ハイライトを同期するだけになる。

合成テキストは `Paragraph.reading` ── ルビを読みとして採用した文なので、
難読漢字を誤読しない。これが事前合成でも効く、青空文庫の注記形式の利点。

エンジン（生成時のみ使用。読者アプリはネット・エンジン不要）:
- VoicevoxEngine … ローカルREST（http://127.0.0.1:50021）。高品質・キャラ音声・オフライン
- EdgeEngine     … edge-tts（[audio]エクストラ）。ニューラル日本語音声・要ネットワーク

エンコードに ffmpeg（外部コマンド）を使う。無ければ明確なエラーを出す。

    from pybunko import Library
    from pybunko.audio import EdgeEngine, build_audiobook
    doc = Library().search('走れメロス')[0].document()
    build_audiobook(doc, 'merosu', engine=EdgeEngine())   # → merosu.opus / merosu.audiobook.json

    # CLI
    python -m pybunko.audio 1567_ruby_4948.zip -o out/merosu
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

from .parser import Document

_STRIP_RE = re.compile(r'[※〔〕｜]')

MANIFEST_VERSION = 1


class VoicevoxEngine:
    """VOICEVOX ローカルREST。起動しておくこと（https://voicevox.hiroshiba.jp/）。

    音声の利用条件（クレジット表記等）は選択キャラクターの規約に従う。
    """
    name = 'voicevox'
    ext = 'wav'

    def __init__(self, host: str = 'http://127.0.0.1:50021', speaker: int = 3):
        self.host = host
        self.speaker = speaker
        self.voice = f'speaker:{speaker}'

    def synth(self, text: str, out_path: str) -> None:
        q = urllib.request.urlopen(urllib.request.Request(
            f'{self.host}/audio_query?speaker={self.speaker}'
            f'&text={urllib.parse.quote(text)}', method='POST'), timeout=60).read()
        wav = urllib.request.urlopen(urllib.request.Request(
            f'{self.host}/synthesis?speaker={self.speaker}',
            data=q, headers={'Content-Type': 'application/json'},
            method='POST'), timeout=300).read()
        Path(out_path).write_bytes(wav)


class OpenAiSpeechEngine:
    """OpenAI互換 /v1/audio/speech を話すローカルTTSサーバ用（標準ライブラリのみ）。

    想定: 自宅のAIマシン（例: MS-S1 MAX）で Kokoro-FastAPI / openedai-speech 等を
    起動し、その base_url を指す。生成もローカルで完結し、クラウド依存が消える。

        engine = OpenAiSpeechEngine('http://ms-s1:8880/v1', voice='jf_alpha')
    """
    name = 'openai-speech'
    ext = 'wav'

    def __init__(self, base_url: str, voice: str = 'alloy',
                 model: str = 'tts-1', response_format: str = 'wav',
                 api_key: str | None = None):
        self.base_url = base_url.rstrip('/')
        self.voice = voice
        self.model = model
        self.ext = response_format
        self.api_key = api_key

    def synth(self, text: str, out_path: str) -> None:
        body = json.dumps({
            'model': self.model, 'input': text, 'voice': self.voice,
            'response_format': self.ext,
        }).encode('utf-8')
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        req = urllib.request.Request(f'{self.base_url}/audio/speech',
                                     data=body, headers=headers, method='POST')
        data = urllib.request.urlopen(req, timeout=300).read()
        Path(out_path).write_bytes(data)


class EdgeEngine:
    """edge-tts（ニューラル日本語音声・生成時のみネットワーク使用）。"""
    name = 'edge-tts'
    ext = 'mp3'

    def __init__(self, voice: str = 'ja-JP-NanamiNeural', rate: str = '-10%'):
        self.voice = voice
        self.rate = rate  # 朗読向けにやや遅め

    def synth(self, text: str, out_path: str) -> None:
        import asyncio

        import edge_tts

        async def _run():
            tts = edge_tts.Communicate(text, self.voice, rate=self.rate)
            await tts.save(out_path)

        asyncio.run(_run())


def _require_ffmpeg() -> None:
    if shutil.which('ffmpeg') is None or shutil.which('ffprobe') is None:
        raise RuntimeError('ffmpeg/ffprobe が必要です（音声の結合とOpus圧縮に使用）')


def _duration(path: str) -> float:
    out = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'csv=p=0', path],
        capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def speech_paragraphs(doc: Document) -> list[tuple[int, str]]:
    """読み上げ対象の (段落index, 読みテキスト) 列。空段落・挿絵はスキップ。"""
    out = []
    for i, p in enumerate(doc.paragraphs):
        text = _STRIP_RE.sub('', p.reading).strip()
        if text:
            out.append((i, text))
    return out


def build_audiobook(doc: Document, out_base: str, engine,
                    bitrate: str = '32k',
                    limit: int | None = None,
                    progress=None) -> dict:
    """Document → 朗読パック（{out_base}.opus ＋ {out_base}.audiobook.json）。

    manifest は段落indexごとの開始秒・長さを持ち、アプリ側の
    段落ハイライト同期・目次ジャンプ（音声側シーク）に使う。
    """
    _require_ffmpeg()
    targets = speech_paragraphs(doc)
    if limit is not None:
        targets = targets[:limit]
    if not targets:
        raise ValueError('読み上げ対象の段落がありません')

    out_base = str(out_base)
    paras = []
    with tempfile.TemporaryDirectory(prefix='pybunko-audio-') as tmp:
        seg_paths = []
        t = 0.0
        for n, (i, text) in enumerate(targets):
            seg = f'{tmp}/{n:05d}.{engine.ext}'
            engine.synth(text, seg)
            dur = _duration(seg)
            paras.append({'i': i, 'start': round(t, 3), 'dur': round(dur, 3)})
            t += dur
            seg_paths.append(seg)
            if progress:
                progress(n + 1, len(targets))
        # 結合 → Opus（モノラル・低ビットレートでも朗読は十分明瞭）
        listfile = f'{tmp}/list.txt'
        Path(listfile).write_text(
            ''.join(f"file '{p}'\n" for p in seg_paths), encoding='utf-8')
        subprocess.run(
            ['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0',
             '-i', listfile, '-ac', '1', '-c:a', 'libopus', '-b:a', bitrate,
             f'{out_base}.opus'],
            check=True)

    manifest = {
        'version': MANIFEST_VERSION,
        'title': doc.title,
        'author': doc.author,
        'engine': engine.name,
        'voice': engine.voice,
        'audio': Path(f'{out_base}.opus').name,
        'total': round(sum(p['dur'] for p in paras), 3),
        'paras': paras,
    }
    Path(f'{out_base}.audiobook.json').write_text(
        json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
    return manifest


def main(argv=None) -> int:
    import argparse

    from .convert import read_text
    from .parser import parse

    ap = argparse.ArgumentParser(
        prog='pybunko.audio',
        description='注記付きテキストから朗読パック（Opus＋段落manifest）を事前生成する')
    ap.add_argument('input', help='注記付きテキスト（.txt / .zip / URL）')
    ap.add_argument('-o', '--out', required=True,
                    help='出力ベース名（→ <out>.opus / <out>.audiobook.json）')
    ap.add_argument('--engine', choices=['edge', 'voicevox', 'openai'], default='edge')
    ap.add_argument('--voice', default=None,
                    help='edge: ja-JP-NanamiNeural 等 / voicevox: speaker番号 / openai: サーバ側の音声名')
    ap.add_argument('--base-url', default='http://127.0.0.1:8880/v1',
                    help='openaiエンジンのエンドポイント（MS-S1 MAX等のローカルTTSサーバ）')
    ap.add_argument('--limit', type=int, default=None,
                    help='先頭N段落のみ（試作用）')
    a = ap.parse_args(argv)

    doc = parse(read_text(a.input))
    if a.engine == 'voicevox':
        engine = VoicevoxEngine(speaker=int(a.voice) if a.voice else 3)
    elif a.engine == 'openai':
        engine = OpenAiSpeechEngine(a.base_url, voice=a.voice or 'alloy')
    else:
        engine = EdgeEngine(voice=a.voice or 'ja-JP-NanamiNeural')

    def progress(done, total):
        print(f'\r合成中 {done}/{total} 段落', end='', flush=True)

    m = build_audiobook(doc, a.out, engine, limit=a.limit, progress=progress)
    print(f"\n✓ {m['title']}: {m['audio']}（{m['total']:.0f}秒・{len(m['paras'])}段落）"
          f" / manifest={a.out}.audiobook.json")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
