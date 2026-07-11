"""aozorabunko — 青空文庫をPythonから。

正本（GitHubミラーの静的テキスト）だけに依存し、
検索・パース・HTML/EPUB/読み上げテキスト変換を手元で行うライブラリ。

>>> from aozorabunko import Library
>>> lib = Library()
>>> work = lib.search('走れメロス')[0]
>>> doc = work.document()
>>> doc.to_epub('merosu.epub')
"""
from .catalog import Library, Work, MIRROR
from .parser import parse, Document, Paragraph
from . import gaiji

__version__ = '0.1.0'
__all__ = ['Library', 'Work', 'parse', 'Document', 'Paragraph', 'MIRROR', 'gaiji']
