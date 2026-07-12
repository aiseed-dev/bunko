"""ndl.py（NDL読みコーパス連携）のテスト。READMEに載っている実例で検証する。"""
import sqlite3

from pybunko import parse
from pybunko.audio import speech_paragraphs
from pybunko.ndl import (apply_readings, corpus_keys, mark_reading_corpus,
                         parse_annotation)

# コーパスREADMEの「こころ」の抜粋そのまま（タブ区切り）
ANNOTATION = """\
行番号 15 0000037.mp3
私は多少の金を区面して出かけることにした。
私は多少の金を工面して、出掛ける事にした。
「解析結果:」
工面\t区面\tくめん\t同音_rubi
出掛\t出か\tでか\t同音_rubi
事\tこと\tこと\t同音_mo
「読み推定結果:」
私\tわたし\tわたし\t私
多少\tたしょう\tたしょう\t多少
金\tかね\tきん\t金
工面\tくめん\tくめん\t区面
出掛\tでか\tでか\t出か
事\tこと\tこと\tこと
"""


def test_parse_annotation_readme_example():
    r = parse_annotation(ANNOTATION)
    assert r['工面'] == 'くめん'
    assert r['金'] == 'かね'      # 推定読み（かね）であり形態素読み（きん）でない
    assert r['事'] == 'こと'
    assert 'こと' not in r        # 漢字を含まない表記は入れない
    assert '区面' not in r        # 解析結果の節は読み辞書に入れない


def test_apply_readings_longest_first():
    r = {'出': 'しゅつ', '出掛': 'でか', '工面': 'くめん'}
    # 「出掛」が「出」より先に引かれる（長い表記優先）
    assert apply_readings('金を工面して出掛ける', r) == '金をくめんしてでかける'
    assert apply_readings('そのまま', {}) == 'そのまま'


def test_speech_paragraphs_ruby_wins_over_dict():
    doc = parse('題\n著\n\n工面《さんだん》した金で、工面する。\n')
    readings = parse_annotation(ANNOTATION)
    text = speech_paragraphs(doc, readings=readings)[0][1]
    # ルビのある「工面」はルビ（さんだん）、無い方は辞書（くめん）
    assert 'さんだん' in text and 'くめん' in text
    assert text.count('工面') == 0


def test_mark_reading_corpus_matching(tmp_path):
    db = tmp_path / 'a.db'
    con = sqlite3.connect(db)
    con.execute('CREATE TABLE works (work_id TEXT PRIMARY KEY, '
                'title TEXT, author TEXT)')
    con.executemany('INSERT INTO works VALUES (?,?,?)', [
        ('1', 'こころ', '夏目漱石'),
        ('2', 'レ・ミゼラブル', 'ユゴーヴィクトル'),   # NDL側は「レミゼラブル_03序」
        ('3', '対象外の作品', '誰か'),
    ])
    con.commit(); con.close()
    rows = [
        {'著者名': '夏目漱石', '作品名': 'こころ'},
        {'著者名': 'ユゴー_ヴィクトル', '作品名': 'レミゼラブル_03序'},
    ]
    n = mark_reading_corpus(str(db), rows=rows)
    assert n == 2
    con = sqlite3.connect(db)
    got = dict(con.execute('SELECT work_id, reading_corpus FROM works'))
    assert got == {'1': 1, '2': 1, '3': 0}
    # 再実行しても冪等（フラグは付け直し）
    assert mark_reading_corpus(str(db), rows=rows) == 2
    con.close()


def test_corpus_keys_normalization():
    keys = corpus_keys([{'著者名': 'アンデルセン_ハンス・クリスチャン',
                         '作品名': '絵のない絵本_01絵のない絵本'}])
    assert ('アンデルセンハンスクリスチャン', '絵のない絵本') in keys
