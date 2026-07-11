"""catalog.py — 作品カタログ（検索・取得・キャッシュ）

データ源は aozorabunko/aozorabunko GitHubミラーの静的ファイルのみ。
公式サーバー（aozora.gr.jp）には一切アクセスしない。
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

MIRROR = 'https://raw.githubusercontent.com/aozorabunko/aozorabunko/master/'
CATALOG_URL = MIRROR + 'index_pages/list_person_all_extended_utf8.zip'
_AOZORA_URL_RE = re.compile(r'https?://www\.aozora\.gr\.jp/(cards/.+)')


def default_cache_dir() -> Path:
    return Path.home() / '.cache' / 'aozorabunko'


@dataclass(frozen=True)
class Work:
    """作品1件。text() で本文（注記付きテキスト）を取得する。"""
    work_id: str
    title: str
    title_yomi: str
    author: str
    author_yomi: str
    card_url: str
    text_url: str
    copyrighted: bool
    _cache_dir: Path = field(repr=False, compare=False,
                             default_factory=default_cache_dir)

    @property
    def mirror_url(self) -> str:
        m = _AOZORA_URL_RE.match(self.text_url)
        return MIRROR + m.group(1) if m else self.text_url

    def text(self) -> str:
        """注記付きテキスト（正本）を返す。取得結果はローカルにキャッシュ。"""
        cache = self._cache_dir / self.mirror_url.rsplit('/', 1)[-1]
        data = _fetch(self.mirror_url, cache)
        if data[:2] == b'PK':
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                name = next(n for n in zf.namelist() if n.endswith('.txt'))
                data = zf.read(name)
        return data.decode('shift_jis', errors='replace')

    def document(self):
        """パース済みDocument（タイトル・著者・段落構造）を返す。"""
        from .parser import parse
        # 挿絵はテキストと同じ files/ ディレクトリ（ミラー）を基準に解決する
        image_base = self.mirror_url.rsplit('/', 1)[0] + '/'
        return parse(self.text(), image_base=image_base)


class Library:
    """青空文庫の全作品カタログ。

    >>> lib = Library()
    >>> works = lib.search('走れメロス')
    >>> print(works[0].document().to_html())
    """

    def __init__(self, cache_dir: Path | str | None = None,
                 public_domain_only: bool = True):
        self.cache_dir = Path(cache_dir) if cache_dir else default_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.public_domain_only = public_domain_only
        self._works: list[Work] | None = None

    @property
    def works(self) -> list[Work]:
        if self._works is None:
            self._works = self._load()
        return self._works

    def _load(self) -> list[Work]:
        raw = _fetch(CATALOG_URL, self.cache_dir / 'catalog.zip')
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            text = zf.read(zf.namelist()[0]).decode('utf-8-sig')
        works = []
        for row in csv.DictReader(io.StringIO(text)):
            if row['役割フラグ'] != '著者' or not row['テキストファイルURL']:
                continue
            copyrighted = (row['作品著作権フラグ'] == 'あり'
                           or row['人物著作権フラグ'] == 'あり')
            if self.public_domain_only and copyrighted:
                continue
            works.append(Work(
                work_id=row['作品ID'],
                title=row['作品名'], title_yomi=row['作品名読み'],
                author=f"{row['姓']}{row['名']}",
                author_yomi=f"{row['姓読み']}{row['名読み']}",
                card_url=row['図書カードURL'],
                text_url=row['テキストファイルURL'],
                copyrighted=copyrighted,
                _cache_dir=self.cache_dir))
        return works

    def search(self, query: str, limit: int = 20) -> list[Work]:
        """作品名・著者名・よみ の部分一致検索。"""
        q = query.strip()
        if not q:
            return []
        hits = [w for w in self.works
                if q in w.title or q in w.title_yomi
                or q in w.author or q in w.author_yomi]
        hits.sort(key=lambda w: (w.title != q, not w.title.startswith(q),
                                 w.author != q, w.title_yomi))
        return hits[:limit]

    def by_author(self, author: str) -> list[Work]:
        return [w for w in self.works
                if author in w.author or author in w.author_yomi]

    def export_parquet(self, path: str, works: list[Work] | None = None,
                       granularity: str = 'paragraph',
                       limit: int | None = None) -> str:
        """作品コーパスを Parquet に書き出す（要 `[parquet]` エクストラ）。

        granularity='paragraph'（段落1件=1行）/ 'work'（作品1件=1行）。
        取得はキャッシュ経由。取得やパースに失敗した作品はスキップする。
        """
        from . import corpus
        targets = list(works if works is not None else self.works)
        if limit is not None:
            targets = targets[:limit]
        rows: list[dict] = []
        for w in targets:
            try:
                doc = w.document()
            except Exception:
                continue  # 取得・パース不能な作品は飛ばす（全体を止めない）
            if granularity == 'work':
                rows.append(corpus.work_row(w, doc))
            else:
                rows.extend(corpus.paragraph_rows(w, doc))
        return corpus.to_parquet(rows, path)

    def export_json(self, path: str, works: list[Work] | None = None,
                    limit: int | None = None) -> str:
        """コーパスを JSONL（1作品1行）で書き出す。標準ライブラリのみ・依存なし。

        各行は構造化Unicodeデータ（外字解決済み・ルビは読みデータ）。
        「残すべき一次データ」を素直に資産化する形。取得失敗作品はスキップ。
        """
        import json
        from . import corpus
        targets = list(works if works is not None else self.works)
        if limit is not None:
            targets = targets[:limit]
        n = 0
        with open(path, 'w', encoding='utf-8') as f:
            for w in targets:
                try:
                    doc = w.document()
                except Exception:
                    continue
                f.write(json.dumps(corpus.work_json_row(w, doc),
                                   ensure_ascii=False) + '\n')
                n += 1
        return path


def _fetch(url: str, cache: Path) -> bytes:
    if cache.exists():
        return cache.read_bytes()
    cache.parent.mkdir(parents=True, exist_ok=True)
    data = urllib.request.urlopen(url).read()
    cache.write_bytes(data)
    return data
