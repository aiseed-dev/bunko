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
em.bouten { font-style: normal;
  text-emphasis: filled sesame; -webkit-text-emphasis: filled sesame; }
'''


_MIDASHI_SIZE_NAME = {2: 'o', 3: 'naka', 4: 'ko'}   # 大 / 中 / 小
_MIDASHI_TYPE_PREFIX = {'mado': 'mado-', 'dogyo': 'dogyo-'}


def midashi_class(level: int, type_: str | None) -> str:
    """見出しのCSSクラス名（aozora2html互換: o-midashi / mado-ko-midashi 等）。"""
    return _MIDASHI_TYPE_PREFIX.get(type_, '') + _MIDASHI_SIZE_NAME[level] + '-midashi'


def to_html(doc: Document) -> str:
    """本文をHTML断片に（<ruby>タグ使用）"""
    out = []
    for p in doc.paragraphs:
        inner = ''.join(
            f'<ruby>{html.escape(t)}<rt>{html.escape(r)}</rt></ruby>'
            if r else html.escape(t)
            for t, r in p.segments)
        if p.emphasis:
            for t in p.emphasis:
                inner = inner.replace(html.escape(t),
                                      f'<em class="bouten">{html.escape(t)}</em>', 1)
        if p.heading_level:
            cls = midashi_class(p.heading_level, p.heading_type)
            out.append(f'<h{p.heading_level} class="{cls}">{inner}</h{p.heading_level}>')
        else:
            out.append(f'<p>{inner}</p>')
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
