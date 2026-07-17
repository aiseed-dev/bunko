"""corpus.py — 全作品コーパスの列指向エクスポート（研究・NLP・RAG向け）

パース済み Document を、段落単位／作品単位の行（dict）に平坦化する。
行の生成は標準ライブラリのみ（ゼロ依存）。Parquet 書き出しだけが
optional の `[parquet]`（pyarrow）を使う。

    from pybunko import Library, corpus
    lib = Library()
    lib.export_parquet('aozora.parquet', limit=100)      # 段落単位
    lib.export_parquet('works.parquet', granularity='work')
"""
from __future__ import annotations


def paragraph_rows(work, doc) -> list[dict]:
    """作品 → 段落1件=1行のリスト。構造化した近代日本語コーパスの最小単位。"""
    rows = []
    for i, p in enumerate(doc.paragraphs):
        rows.append({
            'work_id': work.work_id,
            'title': work.title,
            'author': work.author,
            'para_index': i,
            'heading_level': p.heading_level,
            'heading_type': p.heading_type or '',
            'indent': p.indent,
            'align': p.align or '',
            'jizume': p.jizume,
            'has_image': p.image is not None,
            'n_ruby': sum(1 for _t, r in p.segments if r),
            'plain': p.plain,       # プレーンテキスト
            'reading': p.reading,   # ルビを読みとして採用（誤読しないTTS/検索入力）
        })
    return rows


def work_row(work, doc) -> dict:
    """作品 → 1行（書誌＋全文）。作品レベルの分析・全文検索用。"""
    plain = '\n'.join(p.plain for p in doc.paragraphs)
    reading = '\n'.join(p.reading for p in doc.paragraphs)
    return {
        'work_id': work.work_id,
        'title': work.title,
        'title_yomi': work.title_yomi,
        'author': work.author,
        'author_yomi': work.author_yomi,
        'copyrighted': work.copyrighted,
        'n_paragraphs': len(doc.paragraphs),
        'n_chars': len(plain),
        'plain': plain,
        'reading': reading,
    }


def work_json_row(work, doc) -> dict:
    """作品 → 構造化Unicodeデータ1件（書誌＋Document.to_dict）。JSONL一行用。

    外字・アクセント解決済みの実Unicode文字。これが「残すべき一次データ」で、
    Flutter/Dart 等はこれを描くだけで表示でき、他形式も後から生成できる。
    """
    d = doc.to_dict()
    d['work_id'] = work.work_id
    d['title_yomi'] = work.title_yomi
    d['author_yomi'] = work.author_yomi
    d['copyrighted'] = work.copyrighted
    return d


_KANA_ROWS = [
    ('あ', 'あいうえお'), ('か', 'かきくけこがぎぐげご'),
    ('さ', 'さしすせそざじずぜぞ'), ('た', 'たちつてとだぢづでど'),
    ('な', 'なにぬねの'), ('は', 'はひふへほばびぶべぼぱぴぷぺぽ'),
    ('ま', 'まみむめも'), ('や', 'やゆよ'), ('ら', 'らりるれろ'),
    ('わ', 'わゐゑをん'),
]


def _kana_row(yomi: str) -> str:
    """よみの頭文字 → 五十音の行ラベル（あ/か/…/その他）。"""
    head = yomi[:1]
    for label, chars in _KANA_ROWS:
        if head in chars:
            return label
    return 'その他'


def author_index(works) -> list[dict]:
    """作家別の目次データ（書架）。作家をよみ順、作品をよみ順に整列。

    カタログ（作家別作品一覧）から目次ページがすぐ作れる。出力は構造化データで、
    表示（Flutter/ビューア）は別。各作家に五十音の行ラベル(row)を付す。
    """
    from collections import defaultdict
    groups: dict[tuple, list] = defaultdict(list)
    for w in works:
        groups[(w.author_yomi, w.author)].append(w)
    out = []
    for (yomi, name) in sorted(groups):
        ws = sorted(groups[(yomi, name)], key=lambda w: (w.title_yomi, w.title))
        out.append({
            'author': name, 'author_yomi': yomi, 'row': _kana_row(yomi),
            'count': len(ws),
            'works': [{'work_id': w.work_id, 'title': w.title,
                       'title_yomi': w.title_yomi, 'card_url': w.card_url}
                      for w in ws],
        })
    return out


def to_parquet(rows: list[dict], path: str) -> str:
    """行のリストを Parquet ファイルに書き出す（要 `pip install -e '.[parquet]'`）。"""
    import pyarrow as pa
    import pyarrow.parquet as pq
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path)
    return path
