"""コーパス列指向エクスポート（Parquet）テスト。

行生成（paragraph_rows / work_row）は標準ライブラリのみで検証。
Parquet 書き出しは pyarrow が無ければ skip（[parquet] エクストラ）。
"""
import pytest

from pybunko import corpus


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


def test_author_index():
    """作家別目次（書架）: 作家よみ順・作品よみ順・五十音行ラベル。"""
    from pybunko import Work

    def w(title, tyomi, author, ayomi):
        return Work(work_id='0', title=title, title_yomi=tyomi, author=author,
                    author_yomi=ayomi, card_url='c', text_url='t', copyrighted=False)

    works = [
        w('坊っちゃん', 'ぼっちゃん', '夏目漱石', 'なつめそうせき'),
        w('こころ', 'こころ', '夏目漱石', 'なつめそうせき'),
        w('走れメロス', 'はしれめろす', '太宰治', 'だざいおさむ'),
    ]
    idx = corpus.author_index(works)
    assert [a['author'] for a in idx] == ['太宰治', '夏目漱石']   # よみ順
    assert idx[0]['row'] == 'た' and idx[1]['row'] == 'な'        # 五十音行
    natsume = idx[1]
    assert natsume['count'] == 2
    assert [x['title'] for x in natsume['works']] == ['こころ', '坊っちゃん']  # 作品よみ順


def test_export_index_json(tmp_path):
    from pybunko import Library, Work
    lib = Library.__new__(Library)
    works = [Work(work_id='1', title='あ', title_yomi='あ', author='芥川',
                  author_yomi='あくたがわ', card_url='', text_url='', copyrighted=False)]
    out = tmp_path / "index.json"
    lib.export_index_json(str(out), works=works)
    import json
    d = json.loads(out.read_text(encoding='utf-8'))
    assert d['total_authors'] == 1 and d['total_works'] == 1
    assert d['authors'][0]['author'] == '芥川'


def test_export_json_jsonl(merosu_work, tmp_path):
    """export_json は JSONL（1作品1行）で構造化Unicodeデータを書き出す。依存なし。"""
    import json
    from pybunko import Library, Document
    lib = Library.__new__(Library)          # カタログ取得を避ける
    out = tmp_path / "corpus.jsonl"
    lib.export_json(str(out), works=[merosu_work])
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row['work_id'] == '1567' and row['title'] == '走れメロス'
    assert row['title_yomi'] and 'paragraphs' in row
    # 一次データだけで Document を復元でき、ルビも保持
    doc = Document.from_dict(row)
    assert doc.to_speech_text()[0] == 'メロスは激怒した。'


def test_library_export_parquet_offline(merosu_work, tmp_path):
    # Library.export_parquet を、works を明示して（カタログ取得なしで）検証
    pytest.importorskip("pyarrow.parquet")
    from pybunko import Library
    lib = Library.__new__(Library)  # __init__（カタログ）を避ける
    out = tmp_path / "corpus.parquet"
    lib.export_parquet(str(out), works=[merosu_work], granularity='work')
    import pyarrow.parquet as pq
    table = pq.read_table(str(out))
    assert table.num_rows == 1
    assert table.column('title')[0].as_py() == '走れメロス'
