"""図書カード（cardNNNN.html）詳細メタデータのテスト。

同梱の card1567.html（走れメロス・CC BY 4.0）で、パース・Work.card()（キャッシュ
経由＝オフライン）・SQLiteのcard列格納を検証する。
"""
import pathlib

from aozorabunko import card, db

DATA = pathlib.Path(__file__).parent / "data"


def _html() -> str:
    return card.decode_card((DATA / "card1567.html").read_bytes())


def test_parse_card_sections():
    c = card.parse_card(_html())
    assert c['work']['作品名'] == '走れメロス'
    assert c['work']['文字遣い種別'] == '新字新仮名'
    assert c['work']['分類'].startswith('NDC 913')


def test_parse_card_author():
    a = card.parse_card(_html())['authors'][0]
    assert a['作家名'] == '太宰 治'
    assert a['生年'] == '1909-06-19' and a['没年'] == '1948-06-13'
    assert a['分類'] == '著者'


def test_parse_card_books():
    # 底本と底本の親本が別グループになり、それぞれ出版社を持つ
    books = card.parse_card(_html())['books']
    assert books[0]['role'] == '底本' and books[0]['名称'] == '太宰治全集3'
    assert 'ちくま文庫' in books[0]['出版社']
    assert books[1]['role'] == '底本の親本'
    assert books[1]['出版社'] == '筑摩書房'


def test_parse_card_staff_and_files():
    c = card.parse_card(_html())
    assert c['staff'] == {'入力': '金川一之', '校正': '高橋美奈子'}
    files = c['files']
    assert any('1567_ruby_4948.zip' in str(f.values()) for f in files)


def test_work_card_offline(merosu_work):
    """Work.card() はミラーURL→キャッシュ経由（同梱fixtureでオフライン動作）。"""
    c = merosu_work.card()
    assert c['work']['作品名'] == '走れメロス'
    assert c['staff']['入力'] == '金川一之'


def test_db_card_column(tmp_path, merosu_work):
    """card列: JSONのまま格納・取得。docと独立に保持。"""
    p = str(tmp_path / "c.db")
    db.build_catalog([merosu_work], p)
    assert db.load_card(p, '1567') is None
    db.store_card(p, '1567', merosu_work.card())
    got = db.load_card(p, '1567')
    assert got['books'][0]['名称'] == '太宰治全集3'
    st = db.stats(p)
    assert st['cards'] == 1 and st['documents'] == 0
