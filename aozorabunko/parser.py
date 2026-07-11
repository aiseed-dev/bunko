"""parser.py — 青空文庫注記付きテキストのパーサー

正本（注記付きテキスト）を、構造化された Document に変換する。
Document は各出力形式（HTML / EPUB / 読み上げテキスト）の共通中間表現。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from . import gaiji

# ルビ: ｜複合語《よみ》 または 漢字連続《よみ》
RUBY_RE = re.compile(
    r'(?:｜(?P<base1>[^《｜]+)'
    r'|(?P<base2>[\u4E00-\u9FFF\u3005-\u3007\uF900-\uFAFF々〆ヵヶ]+))'
    r'《(?P<ruby>[^》]+)》')
BOUTEN_RE = re.compile(r'(?P<t>.+?)［＃「(?P=t)」に傍点］')
HEADING_RE = re.compile(r'(?P<t>.+?)［＃「(?P=t)」は(?P<lv>大|中|小)見出し］')
NOTE_RE = re.compile(r'［＃[^］]*］')
HEADER_BLOCK_RE = re.compile(
    r'-{10,}\n【テキスト中に現れる記号について】.*?-{10,}\n', re.S)

Segment = tuple[str, str | None]  # (text, ruby or None)


@dataclass
class Paragraph:
    segments: list[Segment]
    heading_level: int = 0      # 0=本文, 2=大見出し, 3=中見出し, 4=小見出し
    emphasis: list[str] = None  # 傍点対象の文字列

    @property
    def plain(self) -> str:
        return ''.join(t for t, _ in self.segments)

    @property
    def reading(self) -> str:
        """ルビを読みとして採用したテキスト（TTS向け）"""
        return ''.join(r if r else t for t, r in self.segments)


@dataclass
class Document:
    title: str
    author: str
    paragraphs: list[Paragraph]
    colophon: str = ''   # 底本情報

    def to_html(self) -> str:
        from .formats import to_html
        return to_html(self)

    def to_epub(self, path: str) -> str:
        from .formats import to_epub
        return to_epub(self, path)

    def to_speech_text(self) -> list[str]:
        from .formats import to_speech_text
        return to_speech_text(self)


def parse(text: str) -> Document:
    """注記付きテキスト全文 → Document"""
    text = text.replace('\r\n', '\n')
    lines = text.split('\n')
    title, author = lines[0].strip(), lines[1].strip()

    body = '\n'.join(lines[2:])
    body = HEADER_BLOCK_RE.sub('', body)
    parts = re.split(r'\n(?=底本[：:])', body, maxsplit=1)
    body, colophon = parts[0], (parts[1].strip() if len(parts) > 1 else '')

    paragraphs = []
    for line in body.split('\n'):
        if not line.strip():
            continue
        line = gaiji.resolve(line)  # 外字を実文字へ（未対応注記の除去より前）
        heading = 0
        m = HEADING_RE.search(line)
        if m:
            heading = {'大': 2, '中': 3, '小': 4}[m.group('lv')]
            line = m.group('t')
        emphasis = [m.group('t') for m in BOUTEN_RE.finditer(line)]
        line = BOUTEN_RE.sub(r'\g<t>', line)
        line = NOTE_RE.sub('', line)  # 未対応注記は安全に除去
        paragraphs.append(Paragraph(
            segments=_split_ruby(line),
            heading_level=heading,
            emphasis=emphasis or None))
    return Document(title=title, author=author,
                    paragraphs=paragraphs, colophon=colophon)


def _split_ruby(line: str) -> list[Segment]:
    segs, pos = [], 0
    for m in RUBY_RE.finditer(line):
        if m.start() > pos:
            segs.append((line[pos:m.start()], None))
        segs.append((m.group('base1') or m.group('base2'), m.group('ruby')))
        pos = m.end()
    if pos < len(line):
        segs.append((line[pos:], None))
    return segs
