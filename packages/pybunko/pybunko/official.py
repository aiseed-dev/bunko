"""official.py — 注記付きテキスト → 青空文庫公式XHTML（旧 pyaozora.converter）

「基本データ（注記付きテキスト）とPythonだけで、公式サイトと同じHTMLを作る」。
パース（注記解釈）は pybunko 本体（parser）に委譲し、ここは公式流儀の
XHTML1.1 ページ（head / metadata / main_text / 底本 / 表記について / 図書カード）
の組み立てに徹する。出力は既存の公式HTMLとゴールデン比較して検証する。

    from pybunko import to_official_html
    html = to_official_html(open('1567_ruby_4948.txt', encoding='shift_jis').read())
"""
from __future__ import annotations

import html as _html
import re as _re

from .parser import parse
from .formats import midashi_class

CRLF = "\r\n"

# 底本ブロックの「青空文庫（URL）」を公式と同じアンカーに
_AOZORA_LINK = _re.compile(r'青空文庫（(https?://[^）]+)）')


def _esc(s: str) -> str:
    return _html.escape(s, quote=False)


# ── 外字の画像モード（公式流儀）──────────────────────────────────
# 公式HTMLは第3・第4水準の外字を <img class="gaiji"> で埋め込む。
# aozorabunko はUnicodeに解決してしまうので、パース前に外字注記を
# 私用領域(PUA)で囲んだトークンに置換し、描画後に公式のimgタグへ差し戻す。
# PUAで囲むので本文中の数字とは衝突しない。
_GAIJI_NOTE = _re.compile(r'※［＃(?P<body>[^］]*)］')
_GAIJI_MENKUTEN = _re.compile(r'([12])-(\d{1,2})-(\d{1,2})')
_TOKEN = _re.compile('([0-9]+)')  # PUAで囲み本文の数字と衝突させない


def _gaiji_image(body: str) -> str:
    """外字注記 → 公式の <img class="gaiji" />（面区点無しは注記スパン）。"""
    m = _GAIJI_MENKUTEN.search(body)
    if m:
        men, ku, ten = int(m.group(1)), int(m.group(2)), int(m.group(3))
        folder = f'{men}-{ku:02d}'
        name = f'{men}-{ku:02d}-{ten:02d}'
        return (f'<img src="../../../gaiji/{folder}/{name}.png" '
                f'alt="※({body})" class="gaiji" />')
    return f'<span class="notes">※({body})</span>'


def _gaiji_font(body: str) -> str:
    """外字注記 → 実Unicode文字（<span class="gaiji">）。現代的なフォント化。

    第3・第4水準はほぼUnicodeに存在するので、画像でなく実文字を出す。
    選択・検索・読み上げが効き、PNG依存も消える。Unicode化できない外字だけ
    注記スパンにフォールバックする。フォントは head の .gaiji で指定。
    """
    from .gaiji import resolve_note_body
    ch = resolve_note_body(body)
    if ch is not None:
        return f'<span class="gaiji">{_esc(ch)}</span>'
    return f'<span class="notes">※({body})</span>'


_GAIJI_RENDER = {'image': _gaiji_image, 'font': _gaiji_font}


def _tokenize_gaiji(text: str, mode: str = 'image') -> tuple[str, list[str]]:
    """外字注記を PUA トークンに置換し、対応するHTML片の表を返す。"""
    render = _GAIJI_RENDER[mode]
    frags: list[str] = []

    def _repl(m: _re.Match) -> str:
        frags.append(render(m.group('body')))
        return f'{len(frags) - 1}'

    return _GAIJI_NOTE.sub(_repl, text), frags


def _detokenize(s: str, imgs: list[str]) -> str:
    return _TOKEN.sub(lambda m: imgs[int(m.group(1))], s)


# ── head / metadata ─────────────────────────────────────────────
_HEAD = (
    '<?xml version="1.0" encoding="Shift_JIS"?>\r\n'
    '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"\r\n'
    '    "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">\r\n'
    '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="ja" >\r\n'
    '<head>\r\n'
    '\t<meta http-equiv="Content-Type" content="text/html;charset=Shift_JIS" />\r\n'
    '\t<meta http-equiv="content-style-type" content="text/css" />\r\n'
    '\t<link rel="stylesheet" type="text/css" href="{css}" />\r\n'
    '\t<title>{title_full}</title>\r\n'
    '\t<script type="text/javascript" src="../../jquery-1.4.2.min.js"></script>\r\n'
    '  <link rel="Schema.DC" href="http://purl.org/dc/elements/1.1/" />\r\n'
    '\t<meta name="DC.Title" content="{title}" />\r\n'
    '\t<meta name="DC.Creator" content="{author}" />\r\n'
    '\t<meta name="DC.Publisher" content="青空文庫" />\r\n'
    '</head>\r\n<body>\r\n<div class="metadata">\r\n'
)

# ── 表記について / 図書カード（固定フッタ） ─────────────────────
_NOTATION_NOTES = (
    '<div class="notation_notes">\r\n<hr />\r\n<br />\r\n'
    '●表記について<br />\r\n<ul>\r\n'
    '\t<li>このファイルは W3C 勧告 XHTML1.1 にそった形式で作成されています。</li>\r\n'
    '</ul>\r\n</div>\r\n'
)
_CARD = (
    '<div id="card">\r\n<hr />\r\n<br />\r\n'
    '<a href="JavaScript:goLibCard();" id="goAZLibCard">●図書カード</a>'
    '<script type="text/javascript" src="../../contents.js"></script>\r\n'
    '<script type="text/javascript" src="../../golibcard.js"></script>\r\n'
    '</div></body>\r\n</html>\r\n'
)


def _ruby_inner(p) -> str:
    """段落のセグメント → 公式ルビ（<rb>…<rp>（</rp><rt>…</rt><rp>）</rp>）付きHTML。"""
    inner = ''.join(
        (f'<ruby><rb>{_esc(t)}</rb><rp>（</rp>'
         f'<rt>{_esc(r)}</rt><rp>）</rp></ruby>') if r else _esc(t)
        for t, r in p.segments)
    for t, cls, tag in (p.decorations or []):
        e = _esc(t)
        inner = inner.replace(e, f'<{tag} class="{cls}">{e}</{tag}>', 1)
    if p.image:
        src, w, h, cap = p.image
        dim = (f' width="{w}"' if w else '') + (f' height="{h}"' if h else '')
        inner = (f'<img class="illustration" src="{_esc(src)}"{dim} '
                 f'alt="{_esc(cap)}" />') + inner
    return inner


def _render_body(text: str, gaiji: str = 'image') -> str:
    """本文（main_text 内側）を公式流儀で組み立てる。"""
    text, frags = _tokenize_gaiji(text, gaiji)  # 外字を先に退避（img/文字へ差し戻す）
    doc = parse(text, keep_blank_lines=True)  # 空行を <br /> として忠実に
    out, counter = ['<br />' + CRLF], 0
    started = False
    for p in doc.paragraphs:
        blank = (not p.segments and not p.heading_level and not p.image
                 and not (p.indent or p.align == 'right' or p.jizume))
        if not started and blank:
            continue          # 本文冒頭の空行は公式に合わせて捨てる
        started = True
        inner = _ruby_inner(p)
        if p.heading_level:
            counter += {2: 100, 3: 10, 4: 1}[p.heading_level]
            tag = f'h{p.heading_level + 1}'          # 大→h3 中→h4 小→h5
            cls = midashi_class(p.heading_level, p.heading_type)
            out.append(f'<{tag} class="{cls}"><a class="midashi_anchor" '
                       f'id="midashi{counter}">{inner}</a></{tag}>' + CRLF)
        elif p.indent or p.align == 'right' or p.jizume:
            classes, styles = [], []
            if p.indent:
                classes.append(f'jisage_{p.indent}')
                styles.append(f'margin-left: {p.indent}em')
            if p.align == 'right':
                styles.append('text-align:right')
                if p.align_offset:
                    classes.append(f'chitsuki_{p.align_offset}')
                    styles.append(f'margin-right: {p.align_offset}em')
            if p.jizume:
                classes.append(f'jizume_{p.jizume}')
                styles.append(f'width: {p.jizume}em')
            out.append(f'<div class="{" ".join(classes)}" '
                       f'style="{"; ".join(styles)}">{inner}</div>' + CRLF)
        else:
            out.append(inner + '<br />' + CRLF)
    return _detokenize(''.join(out), frags)     # トークン → img もしくは実文字


def _render_note_line(line: str, gaiji: str = 'image') -> str:
    """底本・注記行を公式流儀で描画（外字img・ルビrb/rp・青空文庫リンク）。"""
    from .parser import _split_ruby
    line, frags = _tokenize_gaiji(line, gaiji)
    rendered = ''.join(
        (f'<ruby><rb>{_esc(t)}</rb><rp>（</rp>'
         f'<rt>{_esc(r)}</rt><rp>）</rp></ruby>') if r else _esc(t)
        for t, r in _split_ruby(line))
    rendered = _detokenize(rendered, frags)
    return _AOZORA_LINK.sub(r'<a href="\1">青空文庫（\1）</a>', rendered)


def _bibliographical(colophon: str, gaiji: str = 'image') -> str:
    """底本情報ブロック。"""
    lines = [ln for ln in colophon.split('\n') if ln.strip()]
    body = ''.join(_render_note_line(ln, gaiji) + '<br />' + CRLF for ln in lines)
    return ('<div class="bibliographical_information">\r\n<hr />\r\n<br />\r\n'
            + body + '<br />\r\n<br />\r\n</div>\r\n')


_GAIJI_FONT_NAMES = ('"IPAmjMincho","Hiragino Mincho ProN",'
                     '"Noto Serif CJK JP","BIZ UDMincho",serif')


def _gaiji_chars(text: str) -> set[str]:
    """本文中の外字が font モードで解決される実Unicode文字の集合。"""
    from .gaiji import resolve_note_body
    chars: set[str] = set()
    for m in _GAIJI_NOTE.finditer(text):
        ch = resolve_note_body(m.group('body'))
        if ch:
            chars.update(ch)
    return chars


def _gaiji_style(text: str, embed_font) -> str:
    """font モードの head 用 <style>。embed_font 指定時はサブセットを埋め込む。"""
    if embed_font:
        from . import fonts
        chars = _gaiji_chars(text)
        path = embed_font if isinstance(embed_font, str) else fonts.find_source_font()
        if path and chars:
            woff2 = fonts.subset_woff2(path, chars)
            face = fonts.font_face_css(woff2, fallback=_GAIJI_FONT_NAMES)
            return '\t<style type="text/css">\r\n\t' + face + '\t</style>\r\n'
    return ('\t<style type="text/css">\r\n\t.gaiji { font-family: '
            + _GAIJI_FONT_NAMES + '; }\r\n\t</style>\r\n')


def to_official_html(text: str, *, css: str = '../../aozora.css',
                     gaiji: str = 'image', embed_font=None) -> str:
    """注記付きテキスト全文 → 公式XHTML（文字列, CRLF）。

    gaiji='font' で外字を実Unicode文字にし、embed_font でそのグリフを
    サブセット埋め込み（True=元フォント自動探索 / パス文字列=そのフォント）。
    """
    text = text.replace('\r\n', '\n')
    lines = text.split('\n')
    # 公式は先頭行をそのまま使う（末尾スペース等も保持）ので strip しない
    title = lines[0]
    author = lines[1] if len(lines) > 1 else ''

    doc = parse(text)
    head = _HEAD.format(css=css, title=_esc(title), author=_esc(author),
                        title_full=_esc(f'{author} {title}'.strip()))
    if gaiji == 'font':
        head = head.replace('</head>\r\n',
                            _gaiji_style(text, embed_font) + '</head>\r\n')
    metadata = (f'<h1 class="title">{_esc(title)}</h1>\r\n'
                f'<h2 class="author">{_esc(author)}</h2>\r\n'
                '<br />\r\n<br />\r\n</div>\r\n')
    main_open = '<div id="contents" style="display:none"></div><div class="main_text">'
    body = _render_body(text, gaiji)
    main_close = '</div>\r\n'
    biblio = _bibliographical(doc.colophon, gaiji) if doc.colophon else ''
    return (head + metadata + main_open + body + main_close
            + biblio + _NOTATION_NOTES + _CARD)


def to_official_bytes(text: str, **kwargs) -> bytes:
    """公式XHTMLを Shift_JIS バイト列で返す（公式ファイルと同じ符号化）。"""
    return to_official_html(text, **kwargs).encode('shift_jis', errors='replace')
