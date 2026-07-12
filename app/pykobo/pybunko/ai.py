"""ai.py — Claude による入力・校正支援（標準ライブラリのみ）。

工房（青空工房）の「Claudeを使って便利にする」部分。機械チェック
（kosei.py）が拾えない**意味レベル**の疑いを Claude に探させる:

  - 文脈上おかしい文字（OCR誤読・誤変換・脱字）……「意昧」「人問」の類
  - ルビと本文の不一致（読みとして成立しない疑い）
  - 注記形式の使い方の誤り（作業マニュアル【入力編】の規則に照らして）

設計の約束:
  - Claude は「疑いの提示」まで。採否は必ず人間が底本と突き合わせて決める
    （校正の基本は原稿尊重。勝手な編集はしない）。
  - 依存は標準ライブラリのみ（audio.py のエンジン群と同じ流儀）。
  - 接続先は ANTHROPIC_BASE_URL で差し替え可能（テストは偽サーバ）。
    APIキーは ANTHROPIC_API_KEY 環境変数から。
"""
from __future__ import annotations

import json
import os
import re
import urllib.request

DEFAULT_MODEL = 'claude-fable-5'

# 校正編・入力編マニュアルの要点を蒸留したシステムプロンプト。
KOSEI_SYSTEM = """\
あなたは青空文庫の校正支援者。入力者が作った注記テキストの断片を読み、
「底本と突き合わせて確認すべき疑い」だけを指摘する。

守ること（青空文庫作業マニュアル【校正編】より）:
- 校正は「原稿（底本）尊重」。文章の良し悪しではなく「文字面」を見る。
  現代の目で不自然でも、作者の書き癖・当時の表記は誤りではない。
  仮名づかい・送り仮名・漢字の当て方の「揺れ」は指摘しない。
- 探すのは: OCR誤読（形の似た字: 昧/味、問/間、夕/タ、口/ロ など）、
  誤変換、脱字・衍字、ルビ《》と本文の明白な不整合、
  注記［＃…］の形式が作業マニュアルの書式から外れているもの。
- 確信が持てないものは出さない。数を稼がない。ゼロ件でよい。

出力は JSON 配列のみ（前置き・後書きなし）。各要素:
{"quote": "本文の該当箇所（原文のまま短く）",
 "suspect": "疑わしい文字列",
 "suggestion": "修正案（不明なら空文字）",
 "reason": "疑う理由（一文）"}
疑いが無ければ [] を返す。"""


class ClaudeClient:
    """Anthropic Messages API の最小クライアント（stdlibのみ）。"""

    def __init__(self, api_key: str | None = None,
                 base_url: str | None = None,
                 model: str | None = None):
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY', '')
        self.base_url = (base_url or os.environ.get('ANTHROPIC_BASE_URL')
                         or 'https://api.anthropic.com').rstrip('/')
        self.model = model or os.environ.get('CLAUDE_MODEL', DEFAULT_MODEL)

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def message(self, prompt: str, system: str = '',
                max_tokens: int = 4000, timeout: int = 300) -> str:
        """1往復のメッセージ。返り値はテキストブロックの連結。"""
        if not self.api_key:
            raise RuntimeError('ANTHROPIC_API_KEY が設定されていません')
        body = {'model': self.model, 'max_tokens': max_tokens,
                'messages': [{'role': 'user', 'content': prompt}]}
        if system:
            body['system'] = system
        req = urllib.request.Request(
            f'{self.base_url}/v1/messages',
            data=json.dumps(body).encode('utf-8'),
            headers={'content-type': 'application/json',
                     'x-api-key': self.api_key,
                     'anthropic-version': '2023-06-01'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode('utf-8'))
        return ''.join(b.get('text', '') for b in data.get('content', [])
                       if b.get('type') == 'text')


def _chunks(text: str, size: int = 3000) -> list[str]:
    """段落境界（空行優先、なければ改行）で size 文字前後に分割。"""
    out: list[str] = []
    buf: list[str] = []
    n = 0
    for para in text.replace('\r\n', '\n').split('\n'):
        if n + len(para) > size and buf:
            out.append('\n'.join(buf))
            buf, n = [], 0
        buf.append(para)
        n += len(para) + 1
    if buf:
        out.append('\n'.join(buf))
    return out


def _parse_findings(reply: str) -> list[dict]:
    """Claudeの返答から JSON 配列を取り出す（前後の文章は捨てる）。"""
    m = re.search(r'\[.*\]', reply, re.S)
    if not m:
        return []
    try:
        items = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    return [i for i in items if isinstance(i, dict) and i.get('quote')]


def proofread(text: str, client: ClaudeClient | None = None,
              chunk_size: int = 3000,
              progress=None) -> list[dict]:
    """テキスト全体をClaudeで校正。疑いのリスト（dict）を返す。

    各 dict: quote / suspect / suggestion / reason ＋ chunk（何番目の断片か）。
    progress にコールバックを渡すと (done, total) で進捗を通知する。
    """
    client = client or ClaudeClient()
    chunks = _chunks(text, chunk_size)
    findings: list[dict] = []
    for i, chunk in enumerate(chunks):
        reply = client.message(
            f'次の青空文庫注記テキスト断片を校正してください。\n'
            f'----\n{chunk}\n----', system=KOSEI_SYSTEM)
        for f in _parse_findings(reply):
            f['chunk'] = i
            findings.append(f)
        if progress:
            progress(i + 1, len(chunks))
    return findings


def locate(findings: list[dict], text: str) -> list[dict]:
    """quote から行番号を引き当てて 'line' を付与する（見つからなければ0）。"""
    lines = text.replace('\r\n', '\n').split('\n')
    for f in findings:
        q = f.get('quote', '')
        f['line'] = next((i for i, ln in enumerate(lines, 1) if q and q in ln), 0)
    return findings
