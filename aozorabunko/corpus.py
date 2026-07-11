"""corpus.py — 全作品コーパスの列指向エクスポート（研究・NLP・RAG向け）

パース済み Document を、段落単位／作品単位の行（dict）に平坦化する。
行の生成は標準ライブラリのみ（ゼロ依存）。Parquet 書き出しだけが
optional の `[parquet]`（pyarrow）を使う。

    from aozorabunko import Library, corpus
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


def to_parquet(rows: list[dict], path: str) -> str:
    """行のリストを Parquet ファイルに書き出す（要 `pip install aozorabunko[parquet]`）。"""
    import pyarrow as pa
    import pyarrow.parquet as pq
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path)
    return path
