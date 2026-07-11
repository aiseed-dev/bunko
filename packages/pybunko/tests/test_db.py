"""SQLite（メタデータ）＋JSON（本文doc列）のテスト。標準ライブラリのみ・オフライン。"""
from pybunko import db, Work, Library


def _w(wid, title, tyomi, author, ayomi):
    return Work(work_id=wid, title=title, title_yomi=tyomi, author=author,
                author_yomi=ayomi, card_url='c', text_url='t', copyrighted=False)


def test_build_search_authors(tmp_path):
    path = str(tmp_path / "a.db")
    works = [_w('1', 'こころ', 'こころ', '夏目漱石', 'なつめそうせき'),
             _w('2', '羅生門', 'らしょうもん', '芥川龍之介', 'あくたがわりゅうのすけ')]
    db.build_catalog(works, path)
    st = db.stats(path)
    assert st == {'works': 2, 'authors': 2, 'documents': 0, 'cards': 0}
    # メタ検索
    hits = db.search(path, '芥川')
    assert hits and hits[0]['title'] == '羅生門' and hits[0]['row'] == 'あ'
    # 書架（作家よみ順）
    au = db.authors(path)
    assert [a['author'] for a in au] == ['芥川龍之介', '夏目漱石']
    assert au[0]['count'] == 1


def test_document_json_column(tmp_path):
    path = str(tmp_path / "b.db")
    db.build_catalog([_w('1', 'こころ', 'こころ', '夏目漱石', 'なつめ')], path)
    assert db.load_document(path, '1') is None
    # 本文の細部は JSON のまま doc 列へ
    db.store_document(path, '1', {'title': 'こころ', 'paragraphs': [{'seg': [{'t': '私'}]}]})
    got = db.load_document(path, '1')
    assert got['title'] == 'こころ' and got['paragraphs'][0]['seg'][0]['t'] == '私'
    assert db.stats(path)['documents'] == 1
    # 再ビルドしてもメタは更新・docは保持
    db.build_catalog([_w('1', 'こゝろ', 'こころ', '夏目漱石', 'なつめ')], path)
    assert db.search(path, 'こゝろ')[0]['title'] == 'こゝろ'
    assert db.load_document(path, '1')['title'] == 'こころ'   # docは消えない


def test_library_build_sqlite(tmp_path):
    lib = Library.__new__(Library)
    works = [_w('9', '走れメロス', 'はしれめろす', '太宰治', 'だざいおさむ')]
    p = str(tmp_path / "c.db")
    lib.build_sqlite(p, works=works)
    assert db.stats(p)['works'] == 1 and db.search(p, 'メロス')[0]['work_id'] == '9'
