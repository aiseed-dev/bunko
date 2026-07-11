"""pyaozora — 注記付きテキストから青空文庫公式XHTMLを作る。

基本データ（注記付きテキスト）とPythonだけで、公式サイトと同じHTMLを生成し、
リポジトリにある既存の公式HTMLとゴールデン比較して検証する。
パース（注記解釈）は姉妹ライブラリ aozorabunko に委譲する。

>>> from pyaozora import to_official_html
>>> html = to_official_html(text)   # text は注記付きテキスト全文（Shift_JIS復号済み）
"""
from .converter import to_official_html, to_official_bytes

__version__ = '0.1.0'
__all__ = ['to_official_html', 'to_official_bytes']
