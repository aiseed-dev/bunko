#!/usr/bin/env python3
"""
aozora_tts.py — 青空文庫リーダーの音声出力モジュール

ポイント:
- パース済みセグメント (text, ruby) の ruby を「読み」としてTTSに渡す
  → 旧字・難読漢字の誤読を大幅に低減（青空文庫データならでは）
- エンジンは差し替え可能:
    * VOICEVOX (推奨): ローカルREST API (localhost:50021)。高品質な日本語音声
    * pyttsx3 (フォールバック): OS標準音声。追加サーバー不要
- 段落単位で合成 → 再生位置と画面ハイライトを同期しやすい
"""
from __future__ import annotations
import json
import re
import urllib.parse
import urllib.request

Segment = tuple[str, str | None]  # (text, ruby)

# ---------- 読み上げテキスト生成 ----------

_STRIP_RE = re.compile(r'[※〔〕｜]')


def segments_to_speech(segs: list[Segment]) -> str:
    """1段落分のセグメントを、TTS向けの読みテキストに変換。
    ルビがあるものは読み（ルビ）を採用する。"""
    out = []
    for text, ruby in segs:
        out.append(ruby if ruby else text)
    return _STRIP_RE.sub('', ''.join(out)).strip()


def split_sentences(text: str) -> list[str]:
    """「。」「！」「？」で文分割（短い合成単位にして応答性を上げる）"""
    parts = re.split(r'(?<=[。！？])', text)
    return [p for p in (s.strip() for s in parts) if p]


# ---------- エンジン1: VOICEVOX (ローカルREST) ----------

class VoicevoxEngine:
    """VOICEVOXエンジン (https://voicevox.hiroshiba.jp/) を起動しておくこと。
    デスクトップ配布時は VOICEVOX Core を同梱する方法もある。"""

    def __init__(self, host='http://127.0.0.1:50021', speaker=3):  # 3=ずんだもん(ノーマル)
        self.host = host
        self.speaker = speaker

    def synth(self, text: str) -> bytes:
        q = urllib.request.urlopen(urllib.request.Request(
            f'{self.host}/audio_query?speaker={self.speaker}'
            f'&text={urllib.parse.quote(text)}', method='POST')).read()
        wav = urllib.request.urlopen(urllib.request.Request(
            f'{self.host}/synthesis?speaker={self.speaker}',
            data=q, headers={'Content-Type': 'application/json'},
            method='POST')).read()
        return wav  # WAVバイト列


# ---------- エンジン2: pyttsx3 (OS標準・オフライン) ----------

class Pyttsx3Engine:
    """Windows: SAPI5 (Haruka等) / macOS: AVSpeech (Kyoko等) / Linux: espeak-ng"""

    def __init__(self, rate=180):
        import pyttsx3
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', rate)
        # 日本語ボイスがあれば選択
        for v in self.engine.getProperty('voices'):
            langs = [str(l) for l in (v.languages or [])]
            if 'ja' in (v.id or '').lower() or any('ja' in l for l in langs):
                self.engine.setProperty('voice', v.id)
                break

    def synth_to_file(self, text: str, path: str):
        self.engine.save_to_file(text, path)
        self.engine.runAndWait()

    def speak(self, text: str):
        self.engine.say(text)
        self.engine.runAndWait()


# ---------- Flet側との結合イメージ ----------
# reader（ListView）の各段落に対して:
#
#   import threading
#
#   def play_from(idx: int):
#       def worker():
#           for i in range(idx, len(state['paragraphs'])):
#               text = segments_to_speech(state['paragraphs'][i])
#               highlight(i)                # 再生中の段落を強調 + scroll_to
#               for sent in split_sentences(text):
#                   if stop_flag.is_set():
#                       return
#                   wav = engine.synth(sent)      # VOICEVOX
#                   play_wav_blocking(wav)        # simpleaudio / sounddevice等
#       threading.Thread(target=worker, daemon=True).start()
#
# 文単位で合成するので「合成しながら再生」でき、長編でも待たされない。


if __name__ == '__main__':
    # デモ: 走れメロスの冒頭段落を読み上げテキスト化
    import aozora_shinkan as app
    from aozora_shinkan import Work
    w = Work(work_id='035_1567', title='走れメロス', title_yomi='', author='太宰治',
             author_yomi='', card_url='',
             text_url='https://www.aozora.gr.jp/cards/000035/files/1567_ruby_4948.zip',
             copyrighted=False)
    paragraphs = app.parse_paragraphs(app.load_work_text(w))
    speech = segments_to_speech(paragraphs[0])
    print('--- 原文（表示用） ---')
    print(''.join(t for t, _ in paragraphs[0])[:80], '…')
    print('--- 読み上げ用（ルビ置換後） ---')
    print(speech[:80], '…')
    print('--- 文分割 ---')
    for s in split_sentences(speech)[:4]:
        print(' ・', s)
