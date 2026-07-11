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
NOTE_RE = re.compile(r'［＃[^］]*］')

# 見出し ── 大=2/中=3/小=4（heading_level）、種別 normal/dogyo(同行)/mado(窓)。
_MIDASHI_SIZE = {'大': 2, '中': 3, '小': 4}
_MIDASHI_TYPE = {'窓': 'mado', '同行': 'dogyo'}
# 後置（インライン）形式:  序章［＃「序章」は大見出し］
HEADING_INLINE_RE = re.compile(
    r'(?P<t>.+?)［＃「(?P=t)」は(?P<type>同行|窓)?(?P<lv>大|中|小)見出し］')
# 単一行ブロック形式:  ［＃大見出し］序章［＃大見出し終わり］
HEADING_BLOCK_RE = re.compile(
    r'［＃(?P<type>同行|窓)?(?P<lv>大|中|小)見出し］'
    r'(?P<t>.*?)［＃(?:同行|窓)?(?P=lv)見出し終わり］')
# 複数行ブロックの開始・終了
HEADING_OPEN_RE = re.compile(
    r'^［＃(?P<type>同行|窓)?(?P<lv>大|中|小)見出し］(?P<rest>.*)$')
HEADING_CLOSE_RE = re.compile(
    r'(?P<rest>.*?)［＃(?:同行|窓)?(?P<lv>大|中|小)見出し終わり］')
HEADER_BLOCK_RE = re.compile(
    r'-{10,}\n【テキスト中に現れる記号について】.*?-{10,}\n', re.S)

Segment = tuple[str, str | None]  # (text, ruby or None)


@dataclass
class Paragraph:
    segments: list[Segment]
    heading_level: int = 0      # 0=本文, 2=大見出し, 3=中見出し, 4=小見出し
    heading_type: str | None = None  # 'normal' | 'dogyo'(同行) | 'mado'(窓)
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
    pending = None  # 複数行見出しブロックの途中状態
    for raw in body.split('\n'):
        if not raw.strip():
            continue
        line = gaiji.resolve(raw)  # 外字を実文字へ（未対応注記の除去より前）

        # 複数行見出しブロックの継続中
        if pending is not None:
            mc = HEADING_CLOSE_RE.search(line)
            if mc:
                pending['parts'].append(mc.group('rest'))
                paragraphs.append(_make_paragraph(
                    ''.join(pending['parts']),
                    pending['level'], pending['type']))
                pending = None
            else:
                pending['parts'].append(line)
            continue

        # 単一行ブロック見出し  ［＃大見出し］…［＃大見出し終わり］
        mb = HEADING_BLOCK_RE.search(line)
        if mb:
            paragraphs.append(_make_paragraph(
                mb.group('t'), _MIDASHI_SIZE[mb.group('lv')],
                _MIDASHI_TYPE.get(mb.group('type'), 'normal')))
            continue

        # 複数行ブロック見出しの開始
        mo = HEADING_OPEN_RE.match(line)
        if mo and '見出し終わり' not in line:
            pending = {'level': _MIDASHI_SIZE[mo.group('lv')],
                       'type': _MIDASHI_TYPE.get(mo.group('type'), 'normal'),
                       'parts': [mo.group('rest')]}
            continue

        # 後置（インライン）見出し  序章［＃「序章」は大見出し］
        mi = HEADING_INLINE_RE.search(line)
        if mi:
            paragraphs.append(_make_paragraph(
                mi.group('t'), _MIDASHI_SIZE[mi.group('lv')],
                _MIDASHI_TYPE.get(mi.group('type'), 'normal')))
            continue

        paragraphs.append(_make_paragraph(line))

    return Document(title=title, author=author,
                    paragraphs=paragraphs, colophon=colophon)


def _make_paragraph(line: str, heading_level: int = 0,
                    heading_type: str | None = None) -> Paragraph:
    """1本の行テキスト → Paragraph（傍点抽出・未対応注記除去・ルビ分割）。"""
    emphasis = [m.group('t') for m in BOUTEN_RE.finditer(line)]
    line = BOUTEN_RE.sub(r'\g<t>', line)
    line = NOTE_RE.sub('', line)  # 未対応注記は安全に除去
    return Paragraph(
        segments=_split_ruby(line),
        heading_level=heading_level,
        heading_type=heading_type,
        emphasis=emphasis or None)


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
