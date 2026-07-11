"""parser.py — 青空文庫注記付きテキストのパーサー

正本（注記付きテキスト）を、構造化された Document に変換する。
Document は各出力形式（HTML / EPUB / 読み上げテキスト）の共通中間表現。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from . import accent, decorate, gaiji

# ルビ: ｜複合語《よみ》 または 漢字連続《よみ》
RUBY_RE = re.compile(
    r'(?:｜(?P<base1>[^《｜]+)'
    r'|(?P<base2>[\u4E00-\u9FFF\u3005-\u3007\uF900-\uFAFF々〆ヵヶ]+))'
    r'《(?P<ruby>[^》]+)》')
# 装飾: ○○［＃「○○」に傍点／に二重傍線／は太字／の左に傍点 …］
_DECO_KW = '|'.join(decorate.KEYWORDS)
DECORATE_RE = re.compile(
    r'(?P<t>.+?)［＃「(?P=t)」(?:の(?P<dir>右|左|上|下)に|に|は)'
    rf'(?P<kind>{_DECO_KW})］')
# 挿絵: ［＃<説明>（fig…\.png、横W×縦H）入る］
IMG_RE = re.compile(
    r'［＃(?P<cap>[^（］]*)（(?P<file>fig[^、）]+\.png)'
    r'(?:、横(?P<w>\d+)×縦(?P<h>\d+))?）入る］')
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

# 字下げ・地付き・字詰め（レイアウト系, HANDOFF「dir系」）──────────────
# aozora2html: jisage=margin-left, chitsuki=text-align:right, jizume=width。
_NUM = r'[0-9０-９〇一二三四五六七八九十百]+'
_LAYOUT_KW = r'字下げ|字詰め|地付き|字上げ'
_KANJI_DIGIT = {'〇': 0, '一': 1, '二': 2, '三': 3, '四': 4,
                '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
# ブロック開始 ［＃ここから…字下げ］ / 終了 ［＃(ここで)…字下げ終わり］ / 単一行 ［＃…字下げ］
LAYOUT_END_RE = re.compile(rf'［＃(?:ここで)?[^］]*?(?:{_LAYOUT_KW})終わり］')
LAYOUT_START_RE = re.compile(
    rf'［＃ここから(?P<body>[^］]*?(?:{_LAYOUT_KW})[^］]*?)］')
LAYOUT_LINE_RE = re.compile(
    rf'^［＃(?P<body>(?!ここから)(?!ここで)[^］]*?(?:{_LAYOUT_KW})[^］]*?)］')

Segment = tuple[str, str | None]  # (text, ruby or None)


@dataclass
class Paragraph:
    segments: list[Segment]
    heading_level: int = 0      # 0=本文, 2=大見出し, 3=中見出し, 4=小見出し
    heading_type: str | None = None  # 'normal' | 'dogyo'(同行) | 'mado'(窓)
    decorations: list = None    # [(対象文字列, CSSクラス, HTMLタグ)] 傍点・傍線・太字等
    indent: int = 0             # 字下げ幅（em, 左マージン）
    align: str | None = None    # None | 'right'（地付き・字上げ）
    align_offset: int = 0       # 字上げの N（地からN字上げ, 右マージンem）
    jizume: int = 0             # 字詰め幅（em, width）
    image: tuple | None = None  # 挿絵 (src, width, height, caption)

    @property
    def plain(self) -> str:
        return ''.join(t for t, _ in self.segments)

    @property
    def reading(self) -> str:
        """ルビを読みとして採用したテキスト（TTS向け）"""
        return ''.join(r if r else t for t, r in self.segments)

    @property
    def emphasis(self) -> list[str] | None:
        """傍点（sesame_dot）対象の文字列。後方互換のための導出プロパティ。"""
        if not self.decorations:
            return None
        e = [t for t, cls, _ in self.decorations if cls == 'sesame_dot']
        return e or None


@dataclass
class Document:
    title: str
    author: str
    paragraphs: list[Paragraph]
    colophon: str = ''   # 底本情報

    def to_html(self, compat: str | None = None) -> str:
        from .formats import to_html
        return to_html(self, compat=compat)

    def to_epub(self, path: str) -> str:
        from .formats import to_epub
        return to_epub(self, path)

    def to_speech_text(self) -> list[str]:
        from .formats import to_speech_text
        return to_speech_text(self)

    def to_markdown(self) -> str:
        from .formats import to_markdown
        return to_markdown(self)

    def to_washi_html(self, vertical: bool = True, **kwargs) -> str:
        """縦書き等の組版HTML（要 [washi] エクストラ / aiseed-dev washi-md）。"""
        from .formats import to_washi_html
        return to_washi_html(self, vertical=vertical, **kwargs)

    def to_pdf(self, path: str, vertical: bool = True, **kwargs) -> str:
        """PDF組版（washi-md 経由・ヘッドレスChrome必須）。"""
        from .formats import to_pdf
        return to_pdf(self, path, vertical=vertical, **kwargs)

    def to_dict(self) -> dict:
        """素直な dict へ（Flutter/Dart 等がそのまま読める Unicode一次データ）。

        外字・アクセントは解決済みの実Unicode文字。これさえ持っていれば、
        表示（Flutter）も他形式（HTML/EPUB/…）も後から生成できる ── 器ではなく
        このデータが残すべき一次表現。空フィールドは省いて素直・軽量に保つ。
        """
        paras = []
        for p in self.paragraphs:
            d: dict = {'seg': [{'t': t} if r is None else {'t': t, 'r': r}
                               for t, r in p.segments]}
            if p.heading_level:
                d['h'] = p.heading_level
                if p.heading_type:
                    d['htype'] = p.heading_type
            if p.indent:
                d['indent'] = p.indent
            if p.align:
                d['align'] = p.align
                if p.align_offset:
                    d['align_offset'] = p.align_offset
            if p.jizume:
                d['jizume'] = p.jizume
            if p.decorations:
                d['deco'] = [{'t': t, 'cls': c, 'tag': g}
                             for t, c, g in p.decorations]
            if p.image:
                s, w, h, cap = p.image
                d['image'] = {'src': s, 'w': w, 'h': h, 'cap': cap}
            paras.append(d)
        return {'title': self.title, 'author': self.author,
                'colophon': self.colophon, 'paragraphs': paras}

    def to_json(self, *, ensure_ascii: bool = False, **kwargs) -> str:
        """to_dict() を JSON 文字列に（既定は非ASCIIをそのまま＝実Unicode文字）。"""
        import json
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, **kwargs)

    @classmethod
    def from_dict(cls, d: dict) -> 'Document':
        """to_dict() の逆。Unicode一次データから Document を復元（往復可能）。"""
        paras = []
        for pd in d['paragraphs']:
            segs = [(s['t'], s.get('r')) for s in pd['seg']]
            deco = ([(x['t'], x['cls'], x['tag']) for x in pd['deco']]
                    if pd.get('deco') else None)
            img = pd.get('image')
            image = (img['src'], img['w'], img['h'], img['cap']) if img else None
            paras.append(Paragraph(
                segments=segs, heading_level=pd.get('h', 0),
                heading_type=pd.get('htype'), decorations=deco,
                indent=pd.get('indent', 0), align=pd.get('align'),
                align_offset=pd.get('align_offset', 0),
                jizume=pd.get('jizume', 0), image=image))
        return cls(title=d['title'], author=d['author'],
                   paragraphs=paras, colophon=d.get('colophon', ''))


def parse(text: str, image_base: str = '',
          keep_blank_lines: bool = False) -> Document:
    """注記付きテキスト全文 → Document

    image_base: 挿絵ファイルを解決するベースURL（例 ミラーの files/ ディレクトリ）。
                指定時は 挿絵の src を image_base + ファイル名 にする。
    keep_blank_lines: True で空行を空段落（segments=[]）として保持する。
                公式HTMLの <br /> 忠実再現（pyaozora）用。既定は従来どおり空行を捨てる。
    """
    text = text.replace('\r\n', '\n')
    lines = text.split('\n')
    title, author = lines[0].strip(), lines[1].strip()

    body = '\n'.join(lines[2:])
    body = HEADER_BLOCK_RE.sub('', body)
    parts = re.split(r'\n(?=底本[：:])', body, maxsplit=1)
    body, colophon = parts[0], (parts[1].strip() if len(parts) > 1 else '')

    paragraphs = []
    pending = None       # 複数行見出しブロックの途中状態
    layout_stack = []    # 字下げ・地付き・字詰めブロックの入れ子
    for raw in body.split('\n'):
        if not raw.strip():
            if keep_blank_lines and pending is None:
                paragraphs.append(Paragraph(segments=[]))  # 空行マーカー
            continue
        line = gaiji.resolve(raw)   # 外字を実文字へ（未対応注記の除去より前）
        line = accent.resolve(line)  # 欧文アクセント分解 〔e'〕→é

        # 複数行見出しブロックの継続中
        if pending is not None:
            mc = HEADING_CLOSE_RE.search(line)
            if mc:
                pending['parts'].append(mc.group('rest'))
                p = _make_paragraph(''.join(pending['parts']),
                                    pending['level'], pending['type'], image_base)
                _set_layout(p, pending['layout'])
                paragraphs.append(p)
                pending = None
            else:
                pending['parts'].append(line)
            continue

        # レイアウト（字下げ・地付き・字詰め）指示を先に処理し、行から除く
        line, oneline = _apply_layout(line, layout_stack)
        if not line.strip():
            continue  # レイアウト指示だけの行
        layout = _effective_layout(layout_stack, oneline)

        # 単一行ブロック見出し  ［＃大見出し］…［＃大見出し終わり］
        mb = HEADING_BLOCK_RE.search(line)
        if mb:
            p = _make_paragraph(mb.group('t'), _MIDASHI_SIZE[mb.group('lv')],
                                _MIDASHI_TYPE.get(mb.group('type'), 'normal'),
                                image_base)
            _set_layout(p, layout)
            paragraphs.append(p)
            continue

        # 複数行ブロック見出しの開始
        mo = HEADING_OPEN_RE.match(line)
        if mo and '見出し終わり' not in line:
            pending = {'level': _MIDASHI_SIZE[mo.group('lv')],
                       'type': _MIDASHI_TYPE.get(mo.group('type'), 'normal'),
                       'parts': [mo.group('rest')], 'layout': layout}
            continue

        # 後置（インライン）見出し  序章［＃「序章」は大見出し］
        mi = HEADING_INLINE_RE.search(line)
        if mi:
            p = _make_paragraph(mi.group('t'), _MIDASHI_SIZE[mi.group('lv')],
                                _MIDASHI_TYPE.get(mi.group('type'), 'normal'),
                                image_base)
            _set_layout(p, layout)
            paragraphs.append(p)
            continue

        p = _make_paragraph(line, image_base=image_base)
        _set_layout(p, layout)
        paragraphs.append(p)

    return Document(title=title, author=author,
                    paragraphs=paragraphs, colophon=colophon)


def _make_paragraph(line: str, heading_level: int = 0,
                    heading_type: str | None = None,
                    image_base: str = '') -> Paragraph:
    """1本の行テキスト → Paragraph（装飾・挿絵抽出・未対応注記除去・ルビ分割）。"""
    decorations = []
    for m in DECORATE_RE.finditer(line):
        cls, tag = decorate.deco_class(m.group('kind'), m.group('dir'))
        decorations.append((m.group('t'), cls, tag))
    line = DECORATE_RE.sub(r'\g<t>', line)

    image = None
    mimg = IMG_RE.search(line)
    if mimg:
        src = (image_base + mimg.group('file')) if image_base else mimg.group('file')
        w = int(mimg.group('w')) if mimg.group('w') else None
        h = int(mimg.group('h')) if mimg.group('h') else None
        image = (src, w, h, mimg.group('cap') or '')
        line = IMG_RE.sub('', line)

    line = NOTE_RE.sub('', line)  # 未対応注記は安全に除去
    return Paragraph(
        segments=_split_ruby(line),
        heading_level=heading_level,
        heading_type=heading_type,
        decorations=decorations or None,
        image=image)


# ── レイアウト（字下げ・地付き・字詰め）ヘルパー ──────────────────

def _jp_number(s: str) -> int:
    """アラビア・全角・漢数字（十/百つき）を int に。失敗時は0。"""
    t = s.strip().translate(str.maketrans('０１２３４５６７８９', '0123456789'))
    if t.isdigit():
        return int(t)
    total, cur = 0, 0
    for ch in s.strip():
        if ch in _KANJI_DIGIT:
            cur = _KANJI_DIGIT[ch]
        elif ch == '十':
            total += (cur or 1) * 10
            cur = 0
        elif ch == '百':
            total += (cur or 1) * 100
            cur = 0
        else:
            return 0
    return total + cur


def _layout_from_body(body: str) -> dict:
    """注記本文（字下げ指示）→ レイアウト差分 dict。"""
    m = re.search(rf'地から({_NUM})字上げ', body)
    if m:
        return {'align': 'right', 'align_offset': _jp_number(m.group(1))}
    if '地付き' in body or '字上げ' in body:
        return {'align': 'right'}
    m = re.search(rf'({_NUM})字詰め', body)
    if m:
        return {'jizume': _jp_number(m.group(1))}
    m = re.search(rf'({_NUM})字下げ', body)   # 折り返し字下げも最初のNを採用
    if m:
        return {'indent': _jp_number(m.group(1))}
    return {}


def _apply_layout(line: str, stack: list) -> tuple[str, dict]:
    """行からレイアウト注記を除き、stack を更新。単一行指定を返す。"""
    def _end(_m):
        if stack:
            stack.pop()
        return ''
    line = LAYOUT_END_RE.sub(_end, line)

    def _start(m):
        lay = _layout_from_body(m.group('body'))
        if lay:
            stack.append(lay)
        return ''
    line = LAYOUT_START_RE.sub(_start, line)

    oneline = {}
    m = LAYOUT_LINE_RE.match(line)
    if m:
        oneline = _layout_from_body(m.group('body'))
        line = line[m.end():]
    return line, oneline


def _effective_layout(stack: list, oneline: dict | None = None) -> tuple:
    """入れ子スタック＋単一行指定 → (indent, align, align_offset, jizume)。"""
    indent = sum(l.get('indent', 0) for l in stack)
    align, align_offset, jizume = None, 0, 0
    for l in stack:
        if l.get('align'):
            align, align_offset = l['align'], l.get('align_offset', 0)
        if l.get('jizume'):
            jizume = l['jizume']
    if oneline:
        indent += oneline.get('indent', 0)
        if oneline.get('align'):
            align, align_offset = oneline['align'], oneline.get('align_offset', 0)
        if oneline.get('jizume'):
            jizume = oneline['jizume']
    return indent, align, align_offset, jizume


def _set_layout(p: Paragraph, layout: tuple) -> None:
    p.indent, p.align, p.align_offset, p.jizume = layout


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
