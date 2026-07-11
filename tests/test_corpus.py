"""コーパス列指向エクスポート（Parquet）テスト。

行生成（paragraph_rows / work_row）は標準ライブラリのみで検証。
Parquet 書き出しは pyarrow が無ければ skip（[parquet] エクストラ）。
"""
import pytest

from aozorabunko import corpus


def test_paragraph_rows(merosu_work, merosu_doc):
    rows = corpus.paragraph_rows(merosu_work, merosu_doc)
    assert len(rows) == len(merosu_doc.paragraphs)
    r0 = rows[0]
    assert r0['work_id'] == '1567'
    assert r0['title'] == '走れメロス'
    assert r0['para_index'] == 0
    assert 'plain' in r0 and 'reading' in r0
    # ルビ採用でreadingがplainと異なる段落が存在
    assert any(r['plain'] != r['reading'] for r in rows)


def test_work_row(merosu_work, merosu_doc):
    row = corpus.work_row(merosu_work, merosu_doc)
    assert row['work_id'] == '1567'
    assert row['n_paragraphs'] == len(merosu_doc.paragraphs)
    assert row['n_chars'] > 0
    assert row['copyrighted'] is False


def test_to_parquet_roundtrip(merosu_work, merosu_doc, tmp_path):
    pq = pytest.importorskip("pyarrow.parquet")
    rows = corpus.paragraph_rows(merosu_work, merosu_doc)
    out = tmp_path / "merosu.parquet"
    corpus.to_parquet(rows, str(out))
    assert out.exists()
    table = pq.read_table(str(out))
    assert table.num_rows == len(rows)
    assert set(['work_id', 'plain', 'reading', 'heading_level']).issubset(
        set(table.column_names))


def test_library_export_parquet_offline(merosu_work, tmp_path):
    # Library.export_parquet を、works を明示して（カタログ取得なしで）検証
    pytest.importorskip("pyarrow.parquet")
    from aozorabunko import Library
    lib = Library.__new__(Library)  # __init__（カタログ）を避ける
    out = tmp_path / "corpus.parquet"
    lib.export_parquet(str(out), works=[merosu_work], granularity='work')
    import pyarrow.parquet as pq
    table = pq.read_table(str(out))
    assert table.num_rows == 1
    assert table.column('title')[0].as_py() == '走れメロス'
