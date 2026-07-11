#!/usr/bin/env python3
"""
aozora2epub.py — 青空文庫の注記付きテキストを EPUB に変換するミニマルな例

使い方:
    python aozora2epub.py <zipのURL or ローカルzip/txt> [出力.epub]

対応している注記（プロトタイプ範囲）:
  - ルビ:  漢字《かんじ》 / ｜複合語《ふくごうご》
  - 傍点:  ［＃「…」に傍点］
  - 見出し: ［＃「…」は大見出し/中見出し/小見出し］
  - 字下げ・地付きなどその他の ［＃...］ 注記は除去（本文を壊さない）
  - ヘッダの記号説明ブロックと末尾の底本情報を分離
"""
import io
import re
import sys
import zipfile
import urllib.request
from pathlib import Path

from ebooklib import epub

RUBY_RE = re.compile(r'(?:｜(?P<base1>[^《｜]+)|(?P<base2>[\u4E00-\u9FFF\u3005-\u3007\uF900-\uFAFF々〆ヵヶ]+))《(?P<ruby>[^》]+)》')
BOUTEN_RE = re.compile(r'［＃「(?P<t>[^」]+)」に傍点］')
HEADING_RE = re.compile(r'(?P<t>.+?)［＃「(?P=t)」は(?P<lv>大|中|小)見出し］')
NOTE_RE = re.compile(r'［＃[^］]*］')  # 残りの注記は除去


def load_text(src: str) -> str:
    """URL / zip / txt から Shift_JIS テキストを読み込む"""
    if src.startswith('http'):
        data = urllib.request.urlopen(src).read()
    else:
        data = Path(src).read_bytes()

    if src.endswith('.zip') or data[:2] == b'PK':
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            name = next(n for n in zf.namelist() if n.endswith('.txt'))
            data = zf.read(name)
    return data.decode('shift_jis', errors='replace')


def split_sections(text: str):
    """タイトル・著者・本文・底本情報を分離"""
    text = text.replace('\r\n', '\n')
    lines = text.split('\n')
    title, author = lines[0].strip(), lines[1].strip()

    # ヘッダの「記号について」ブロックを除去
    body = '\n'.join(lines[2:])
    body = re.sub(r'-{10,}\n【テキスト中に現れる記号について】.*?-{10,}\n', '', body, flags=re.S)

    # 底本情報（末尾）を分離
    m = re.search(r'\n底本[：:]', body)
    colophon = ''
    if m:
        colophon = body[m.start():].strip()
        body = body[:m.start()]
    return title, author, body.strip(), colophon


def to_html(body: str) -> str:
    """注記付きテキスト → HTML 本文"""
    import html
    body = html.escape(body)

    def ruby_sub(m):
        base = m.group('base1') or m.group('base2')
        return f'<ruby>{base}<rt>{m.group("ruby")}</rt></ruby>'

    body = RUBY_RE.sub(ruby_sub, body)
    body = HEADING_RE.sub(lambda m: {'大': '<h2>', '中': '<h3>', '小': '<h4>'}[m.group('lv')]
                          + m.group('t')
                          + {'大': '</h2>', '中': '</h3>', '小': '</h4>'}[m.group('lv')], body)
    body = BOUTEN_RE.sub(r'<em class="bouten">\g<t></em>', body)
    body = NOTE_RE.sub('', body)  # 未対応注記は落とす

    paragraphs = [f'<p>{line}</p>' for line in body.split('\n') if line.strip()]
    return '\n'.join(paragraphs)


CSS = '''
body { font-family: serif; line-height: 1.9; }
p { text-indent: 0; margin: 0 0 0.3em; }
em.bouten { font-style: normal; text-emphasis: filled sesame; -webkit-text-emphasis: filled sesame; }
/* 縦書きにしたい場合は以下を有効化（Kindleの対応はEPUB3準拠）
html { writing-mode: vertical-rl; -epub-writing-mode: vertical-rl; }
*/
'''


def build_epub(title, author, body_html, colophon, out_path):
    book = epub.EpubBook()
    book.set_identifier(f'aozora-{abs(hash(title + author))}')
    book.set_title(title)
    book.set_language('ja')
    book.add_author(author)

    style = epub.EpubItem(uid='style', file_name='style.css',
                          media_type='text/css', content=CSS)
    book.add_item(style)

    ch = epub.EpubHtml(title=title, file_name='body.xhtml', lang='ja')
    ch.content = f'<h1>{title}</h1><p class="author">{author}</p>{body_html}'
    ch.add_item(style)
    book.add_item(ch)

    items = [ch]
    if colophon:
        col = epub.EpubHtml(title='底本', file_name='colophon.xhtml', lang='ja')
        col.content = '<h2>底本</h2>' + ''.join(
            f'<p>{line}</p>' for line in colophon.split('\n') if line.strip())
        col.add_item(style)
        book.add_item(col)
        items.append(col)

    book.toc = items
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ['nav'] + items
    epub.write_epub(out_path, book)


if __name__ == '__main__':
    src = sys.argv[1]
    text = load_text(src)
    title, author, body, colophon = split_sections(text)
    out = sys.argv[2] if len(sys.argv) > 2 else f'{title}.epub'
    build_epub(title, author, to_html(body), colophon, out)
    print(f'✓ {title} / {author} → {out}')
