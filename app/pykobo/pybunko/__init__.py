"""pybunko — 青空文庫をPythonから（文庫アプリのPython側）。

正本（GitHubミラーの静的テキスト）だけに依存し、
検索・パース・HTML/EPUB/読み上げテキスト変換を手元で行うライブラリ。

>>> from pybunko import Library
>>> lib = Library()
>>> work = lib.search('走れメロス')[0]
>>> doc = work.document()
>>> doc.to_epub('merosu.epub')
"""
from .catalog import Library, Work, MIRROR
from .parser import parse, Document, Paragraph
from . import gaiji, decorate, accent, corpus, convert, db, card, fonts, official
from .convert import to_json, read_text
from .official import to_official_html, to_official_bytes

__version__ = '0.1.0'
__all__ = ['Library', 'Work', 'parse', 'Document', 'Paragraph', 'MIRROR',
           'gaiji', 'decorate', 'accent', 'corpus', 'convert', 'db', 'card',
           'fonts', 'official', 'to_json', 'read_text',
           'to_official_html', 'to_official_bytes']
