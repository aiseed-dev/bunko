"""formats.py — Document から各出力形式への変換

「さまざまなデータ形式で本へのアクセスができるようなしくみ」の実装部。
"""
from __future__ import annotations

import html
import re

from .parser import Document

_CSS = '''
body { font-family: serif; line-height: 1.9; }
p { text-indent: 0; margin: 0 0 0.3em; }
em.sesame_dot, em.white_sesame_dot, em.black_circle, em.white_circle,
em.black_up-pointing_triangle, em.white_up-pointing_triangle,
em.bullseye, em.fisheye, em.saltire { font-style: normal; }
em.sesame_dot   { text-emphasis: filled sesame;        -webkit-text-emphasis: filled sesame; }
em.white_sesame_dot { text-emphasis: open sesame;      -webkit-text-emphasis: open sesame; }
em.black_circle { text-emphasis: filled circle;        -webkit-text-emphasis: filled circle; }
em.white_circle { text-emphasis: open circle;          -webkit-text-emphasis: open circle; }
em.black_up-pointing_triangle { text-emphasis: filled triangle; -webkit-text-emphasis: filled triangle; }
em.white_up-pointing_triangle { text-emphasis: open triangle;   -webkit-text-emphasis: open triangle; }
em.fisheye      { text-emphasis: filled double-circle; -webkit-text-emphasis: filled double-circle; }
em.bullseye     { text-emphasis: open double-circle;   -webkit-text-emphasis: open double-circle; }
em.saltire      { text-emphasis: "\\00D7";             -webkit-text-emphasis: "\\00D7"; }
em[class$="_after"] { font-style: normal;
  text-emphasis: filled sesame; -webkit-text-emphasis: filled sesame;
  text-emphasis-position: under left; -webkit-text-emphasis-position: under left; }
em[class^="underline_"] { font-style: normal; text-decoration-line: underline; }
em[class^="overline_"]  { font-style: normal; text-decoration-line: overline; }
em.underline_double, em.overline_double { text-decoration-style: double; }
em.underline_dotted { text-decoration-style: dotted; }
em.underline_dashed { text-decoration-style: dashed; }
em.underline_wave   { text-decoration-style: wavy; }
span.futoji { font-weight: bold; }
span.shatai { font-style: italic; }
'''


_MIDASHI_SIZE_NAME = {2: 'o', 3: 'naka', 4: 'ko'}   # 大 / 中 / 小
_MIDASHI_TYPE_PREFIX = {'mado': 'mado-', 'dogyo': 'dogyo-'}


def midashi_class(level: int, type_: str | None) -> str:
    """見出しのCSSクラス名（aozora2html互換: o-midashi / mado-ko-midashi 等）。"""
    return _MIDASHI_TYPE_PREFIX.get(type_, '') + _MIDASHI_SIZE_NAME[level] + '-midashi'


def _layout_class_style(p) -> tuple[list[str], list[str]]:
    """段落のレイアウト属性 → (classes, styles)。aozora2html互換のクラス名。"""
    classes, styles = [], []
    if p.indent:
        classes.append(f'jisage_{p.indent}')
        styles.append(f'margin-left: {p.indent}em')
    if p.align == 'right':
        styles.append('text-align: right')
        if p.align_offset:
            classes.append(f'chitsuki_{p.align_offset}')
            styles.append(f'margin-right: {p.align_offset}em')
    if p.jizume:
        classes.append(f'jizume_{p.jizume}')
        styles.append(f'width: {p.jizume}em')
    return classes, styles


def _attr(classes: list[str], styles: list[str]) -> str:
    attr = ''
    if classes:
        attr += f' class="{" ".join(classes)}"'
    if styles:
        attr += f' style="{"; ".join(styles)}"'
    return attr


# 見出しIDの増分（aozora2html MidashiCounter: 大+100 中+10 小+1）
_MIDASHI_INC = {2: 100, 3: 10, 4: 1}


def to_html(doc: Document, compat: str | None = None) -> str:
    """本文をHTML断片に（<ruby>タグ使用）。

    compat=None    … 本ライブラリの意味構造HTML（見出しは h2/h3/h4）
    compat='aozora'… 青空文庫公式流儀（aozora2html互換）。見出しは h3/h4/h5 で
                     `<a class="midashi_anchor" id="midashiN">` を内包し、
                     見出しIDは MidashiCounter（大+100/中+10/小+1）で採番。
    """
    aozora = compat == 'aozora'
    out, counter = [], 0
    for p in doc.paragraphs:
        inner = ''.join(
            f'<ruby>{html.escape(t)}<rt>{html.escape(r)}</rt></ruby>'
            if r else html.escape(t)
            for t, r in p.segments)
        if p.decorations:
            for t, cls, tag in p.decorations:
                esc = html.escape(t)
                inner = inner.replace(
                    esc, f'<{tag} class="{cls}">{esc}</{tag}>', 1)
        if p.image:
            src, w, h, cap = p.image
            dim = (f' width="{w}"' if w else '') + (f' height="{h}"' if h else '')
            inner = (f'<img class="illustration" src="{html.escape(src)}"{dim} '
                     f'alt="{html.escape(cap)}" />') + inner
        classes, styles = _layout_class_style(p)
        if p.heading_level:
            classes.insert(0, midashi_class(p.heading_level, p.heading_type))
            if aozora:
                counter += _MIDASHI_INC[p.heading_level]
                tag = f'h{p.heading_level + 1}'   # 大→h3 中→h4 小→h5
                inner = (f'<a class="midashi_anchor" '
                         f'id="midashi{counter}">{inner}</a>')
            else:
                tag = f'h{p.heading_level}'        # 大→h2 中→h3 小→h4
        else:
            tag = 'p'
        out.append(f'<{tag}{_attr(classes, styles)}>{inner}</{tag}>')
    return '\n'.join(out)


def to_epub(doc: Document, path: str) -> str:
    """EPUB3 ファイルを書き出し、パスを返す（Send to Kindle / Play ブックス対応）"""
    from ebooklib import epub
    book = epub.EpubBook()
    book.set_identifier(f'aozora-{abs(hash(doc.title + doc.author))}')
    book.set_title(doc.title)
    book.set_language('ja')
    book.add_author(doc.author)

    style = epub.EpubItem(uid='style', file_name='style.css',
                          media_type='text/css', content=_CSS)
    book.add_item(style)

    ch = epub.EpubHtml(title=doc.title, file_name='body.xhtml', lang='ja')
    ch.content = (f'<h1>{html.escape(doc.title)}</h1>'
                  f'<p class="author">{html.escape(doc.author)}</p>'
                  + to_html(doc))
    ch.add_item(style)
    book.add_item(ch)
    items = [ch]

    if doc.colophon:
        col = epub.EpubHtml(title='底本', file_name='colophon.xhtml', lang='ja')
        col.content = '<h2>底本</h2>' + ''.join(
            f'<p>{html.escape(line)}</p>'
            for line in doc.colophon.split('\n') if line.strip())
        col.add_item(style)
        book.add_item(col)
        items.append(col)

    book.toc = items
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ['nav'] + items
    epub.write_epub(path, book)
    return path


_SENT_RE = re.compile(r'(?<=[。！？])')
_STRIP_RE = re.compile(r'[※〔〕｜]')


def to_speech_text(doc: Document) -> list[str]:
    """読み上げ用の文リスト。ルビを読みとして採用するので難読漢字を誤読しない。"""
    sentences = []
    for p in doc.paragraphs:
        text = _STRIP_RE.sub('', p.reading).strip()
        sentences += [s.strip() for s in _SENT_RE.split(text) if s.strip()]
    return sentences


# ── washi(pywashi)連携（縦書き・原稿用紙・PDF組版）───────────────
# 依存は [washi] エクストラ（aiseed-dev/pywashi。PyPI名=pywashi・CLI名=washi）。
# 本体のゼロ依存は崩さない。

def to_markdown(doc: Document) -> str:
    """Document → Markdown（dendenルビ `{漢字|かんじ}`）。

    pywashi / mdit-py-cjk-friendly の入力形式。ルビはよみデータとして
    `{base|reading}` に、太字/斜体は **/* に、傍点・傍線（em）は
    mdit-py-cjk-friendly の bouten プラグイン記法 `[対象]{.class}` に、
    その他（sub/sup）はHTMLで渡す。見出しは # の深さで表す。
    """
    lines = []
    for p in doc.paragraphs:
        if p.image:
            src, _w, _h, cap = p.image
            lines += [f'![{cap}]({src})', '']
            continue
        text = ''.join(
            ('{' + t + '|' + r + '}') if r else t for t, r in p.segments)
        for target, cls, tag in (p.decorations or []):
            if cls == 'futoji':
                repl = f'**{target}**'
            elif cls == 'shatai':
                repl = f'*{target}*'
            elif tag == 'em':   # 傍点・傍線 → bouten プラグインのクラス付きスパン
                repl = f'[{target}]{{.{cls}}}'
            else:               # sub/sup 等は washi の html:True で通す
                repl = f'<{tag} class="{cls}">{target}</{tag}>'
            text = text.replace(target, repl, 1)
        if p.heading_level:            # 大=2→#, 中=3→##, 小=4→###
            text = '#' * (p.heading_level - 1) + ' ' + text
        lines += [text, '']
    return '\n'.join(lines).strip() + '\n'


def to_washi_html(doc: Document, vertical: bool = True,
                  genko: bool = False, theme: str = 'default', **kwargs) -> str:
    """washi(pywashi)で縦書き等の組版HTMLを返す（要 `pip install -e 'app/pykobo[washi]'`）。"""
    import pywashi
    return pywashi.render(to_markdown(doc), title=doc.title, author=doc.author,
                          vertical=vertical, genko=genko, theme=theme, **kwargs)


def to_pdf(doc: Document, path: str, vertical: bool = True, **kwargs) -> str:
    """washi(pywashi)経由でPDFを書き出す（ヘッドレスChrome必須）。パスを返す。"""
    import tempfile
    from pathlib import Path

    import pywashi
    html_str = to_washi_html(doc, vertical=vertical, **kwargs)
    with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False,
                                     encoding='utf-8') as f:
        f.write(html_str)
        tmp = Path(f.name)
    pywashi.to_pdf(tmp, Path(path))
    return path
