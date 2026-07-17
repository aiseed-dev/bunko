"""db.py — 図書カード・書架情報を SQLite に、作品本文の細部は JSON のまま。

メタデータ（作家・作品・図書カード・五十音行）は SQLite に入れて検索・グループ化・
結合を速くする。作品本文の構造化データ（Document）は細かいので、正規化せず
`works.doc` 列に **JSON のまま** 載せる（必要になったら取得して埋める）。

依存は標準ライブラリ `sqlite3` のみ ── ゼロ依存を保つ。

    from pybunko import Library
    lib = Library()
    lib.build_sqlite('aozora.db')                 # カタログ（メタデータ）を投入
    lib.build_sqlite('aozora.db', documents=True, limit=100)  # 本文JSONも埋める

    from pybunko import db
    db.search('aozora.db', '芥川')                # メタ検索（速い）
    doc = db.load_document('aozora.db', '000074') # 本文JSON → dict
"""
from __future__ import annotations

import json
import sqlite3

from . import corpus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS works(
  work_id      TEXT PRIMARY KEY,
  title        TEXT, title_yomi  TEXT,
  author       TEXT, author_yomi TEXT,
  row          TEXT,            -- 五十音行（あ/か/…/その他）
  card_url     TEXT, text_url   TEXT,
  copyrighted  INTEGER,
  ndc          TEXT,           -- NDC分類（'913'/'K933'/'756 914'。分野別インデックス用）
  doc          TEXT,            -- 作品本文の構造化データ（JSONのまま）。NULL=未取得
  card         TEXT             -- 図書カード詳細（底本・入力者等, JSONのまま）。NULL=未取得
);
CREATE INDEX IF NOT EXISTS ix_author_yomi ON works(author_yomi);
CREATE INDEX IF NOT EXISTS ix_title_yomi  ON works(title_yomi);
CREATE INDEX IF NOT EXISTS ix_row         ON works(row);
"""


def _migrate(con: sqlite3.Connection) -> None:
    """既存DBに後から増えた列を足す（card列の無い初期DBを更新）。"""
    cols = {r[1] for r in con.execute("PRAGMA table_info(works)")}
    if 'card' not in cols:
        con.execute("ALTER TABLE works ADD COLUMN card TEXT")
    if 'ndc' not in cols:
        con.execute("ALTER TABLE works ADD COLUMN ndc TEXT")

_UPSERT = """
INSERT INTO works
  (work_id,title,title_yomi,author,author_yomi,row,card_url,text_url,copyrighted,ndc)
  VALUES(:work_id,:title,:title_yomi,:author,:author_yomi,:row,:card_url,:text_url,:copyrighted,:ndc)
ON CONFLICT(work_id) DO UPDATE SET
  title=excluded.title, title_yomi=excluded.title_yomi,
  author=excluded.author, author_yomi=excluded.author_yomi, row=excluded.row,
  card_url=excluded.card_url, text_url=excluded.text_url,
  copyrighted=excluded.copyrighted, ndc=excluded.ndc
"""   # doc は上書きしない（本文JSONは保持）


def build_catalog(works, path: str) -> str:
    """作品メタデータ（図書カード・書架情報）を SQLite に投入。本文doc列は保持。"""
    con = sqlite3.connect(path)
    try:
        con.executescript(_SCHEMA)
        _migrate(con)
        con.executemany(_UPSERT, [{
            'work_id': w.work_id, 'title': w.title, 'title_yomi': w.title_yomi,
            'author': w.author, 'author_yomi': w.author_yomi,
            'row': corpus._kana_row(w.author_yomi),
            'card_url': w.card_url, 'text_url': w.text_url,
            'copyrighted': int(w.copyrighted),
            'ndc': getattr(w, 'ndc', ''),
        } for w in works])
        con.commit()
    finally:
        con.close()
    return path


def store_documents(path: str, items) -> int:
    """(work_id, doc) を works.doc に格納。doc は dict か JSON文字列。"""
    rows = [((json.dumps(d, ensure_ascii=False) if not isinstance(d, str) else d), wid)
            for wid, d in items]
    con = sqlite3.connect(path)
    try:
        con.executemany("UPDATE works SET doc=? WHERE work_id=?", rows)
        con.commit()
        return con.total_changes
    finally:
        con.close()


def store_document(path: str, work_id: str, doc) -> None:
    store_documents(path, [(work_id, doc)])


def load_document(path: str, work_id: str) -> dict | None:
    """works.doc（本文JSON）→ dict。未取得なら None。"""
    con = sqlite3.connect(path)
    try:
        r = con.execute("SELECT doc FROM works WHERE work_id=?", (work_id,)).fetchone()
    finally:
        con.close()
    return json.loads(r[0]) if r and r[0] else None


def store_cards(path: str, items) -> int:
    """(work_id, card) を works.card に格納。card は dict か JSON文字列。"""
    rows = [((json.dumps(c, ensure_ascii=False) if not isinstance(c, str) else c), wid)
            for wid, c in items]
    con = sqlite3.connect(path)
    try:
        _migrate(con)
        con.executemany("UPDATE works SET card=? WHERE work_id=?", rows)
        con.commit()
        return con.total_changes
    finally:
        con.close()


def store_card(path: str, work_id: str, card) -> None:
    store_cards(path, [(work_id, card)])


def load_card(path: str, work_id: str) -> dict | None:
    """works.card（図書カード詳細JSON）→ dict。未取得なら None。"""
    con = sqlite3.connect(path)
    try:
        r = con.execute("SELECT card FROM works WHERE work_id=?",
                        (work_id,)).fetchone()
    finally:
        con.close()
    return json.loads(r[0]) if r and r[0] else None


def search(path: str, q: str, limit: int = 30) -> list[dict]:
    """作品名・著者名・よみ の部分一致検索（メタデータのみ・速い）。"""
    # q 中の LIKE ワイルドカード(% _)と escape 記号をリテラル化する
    esc = q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    like = f'%{esc}%'
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT work_id,title,title_yomi,author,author_yomi,row,card_url "
            "FROM works WHERE title LIKE ? ESCAPE '\\' OR title_yomi LIKE ? ESCAPE '\\' "
            "OR author LIKE ? ESCAPE '\\' OR author_yomi LIKE ? ESCAPE '\\' "
            "ORDER BY (title=?) DESC, author_yomi, title_yomi LIMIT ?",
            (like, like, like, like, q, limit)).fetchall()
    finally:
        con.close()
    return [dict(r) for r in rows]


def authors(path: str) -> list[dict]:
    """書架: 作家別の作品数（よみ順・五十音行付き）。SQLで集計。"""
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT author, author_yomi, row, COUNT(*) AS count "
            "FROM works GROUP BY author, author_yomi ORDER BY author_yomi").fetchall()
    finally:
        con.close()
    return [dict(r) for r in rows]


def stats(path: str) -> dict:
    con = sqlite3.connect(path)
    try:
        _migrate(con)
        n = con.execute("SELECT COUNT(*) FROM works").fetchone()[0]
        nd = con.execute("SELECT COUNT(*) FROM works WHERE doc IS NOT NULL").fetchone()[0]
        nc = con.execute("SELECT COUNT(*) FROM works WHERE card IS NOT NULL").fetchone()[0]
        na = con.execute("SELECT COUNT(DISTINCT author||author_yomi) FROM works").fetchone()[0]
    finally:
        con.close()
    return {'works': n, 'authors': na, 'documents': nd, 'cards': nc}
