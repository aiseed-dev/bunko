"""ndl.py — NDL Lab「青空文庫振り仮名注釈付き音声コーパス」との連携。

国立国会図書館 NDL Lab が公開する読みデータ（Public Domain Mark）:
  https://github.com/ndl-lab/hurigana-speech-corpus-aozora
サピエの人間による朗読（音声デイジー）と青空文庫テキストを突き合わせ、
漢字に読み（振り仮名）を付けたもの。3,632作品・録音4,892時間。

ここでの使いみちは2つ:

  1. 書架DBへの「読みコーパスあり」フラグ付け（mark_reading_corpus）
     …… どの作品に人間の朗読由来の読みデータがあるかを可視化する
  2. 朗読パック生成時の読み辞書（parse_annotation → audio.py）
     …… ルビの無い漢字の読みを、TTSエンジンの推測ではなく
     人間の朗読から起こした読みで置き換え、誤読を減らす

読みは「下書き」として使う（コーパス自身が注意書きするとおり、
振り仮名が正確でない場合がある）。ルビがある箇所は常にルビを優先する。
"""
from __future__ import annotations

import csv
import io
import re
import sqlite3
import unicodedata
import urllib.request
from collections import Counter
from pathlib import Path

ALL_WORKS_URL = ('https://raw.githubusercontent.com/ndl-lab/'
                 'hurigana-speech-corpus-aozora/master/all_works.csv')

_NORM_RE = re.compile(r'[_・\s　、，,]')
_KANJI_RE = re.compile(r'[㐀-鿿豈-鶴々〆〇]')


def _norm(s: str) -> str:
    # NFKCで全角英数と半角を寄せる（Ｄ坂／D坂）。区切り記号は落とす
    return _NORM_RE.sub('', unicodedata.normalize('NFKC', s))


def load_all_works(source: str | None = None) -> list[dict]:
    """all_works.csv を読む。source はパス/URL（省略時は GitHub raw）。"""
    src = source or ALL_WORKS_URL
    if src.startswith(('http://', 'https://')):
        data = urllib.request.urlopen(src, timeout=30).read()
    else:
        data = Path(src).read_bytes()
    return list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))


def corpus_keys(rows: list[dict]) -> set[tuple[str, str]]:
    """照合キー (正規化著者, 正規化作品名) の集合。

    NDL側は外国人著者が「姓_名」、長編が「基底名_連番章」に分かれるため、
    正規化（区切り除去）＋基底名（最初の「_」まで）の両方をキーにする。
    """
    keys: set[tuple[str, str]] = set()
    for r in rows:
        a = _norm(r.get('著者名', ''))
        t = r.get('作品名', '')
        if not a or not t:
            continue
        keys.add((a, _norm(t)))
        keys.add((a, _norm(t.split('_')[0])))
    return keys


def mark_reading_corpus(db_path: str, rows: list[dict] | None = None,
                        source: str | None = None) -> int:
    """書架DB（works）に reading_corpus フラグ（0/1）を付ける。

    列が無ければ ALTER で足す。既存フラグは一旦0に戻してから付け直すので、
    コーパス更新後の再実行で増減が正しく反映される。返り値は該当作品数。
    """
    keys = corpus_keys(rows if rows is not None else load_all_works(source))
    con = sqlite3.connect(db_path)
    try:
        cols = {r[1] for r in con.execute('PRAGMA table_info(works)')}
        if 'reading_corpus' not in cols:
            con.execute('ALTER TABLE works ADD COLUMN reading_corpus '
                        'INTEGER NOT NULL DEFAULT 0')
        con.execute('UPDATE works SET reading_corpus = 0')
        hits = [
            (wid,) for wid, title, author in
            con.execute('SELECT work_id, title, author FROM works')
            if (_norm(author), _norm(title)) in keys
        ]
        con.executemany(
            'UPDATE works SET reading_corpus = 1 WHERE work_id = ?', hits)
        con.commit()
        return len(hits)
    finally:
        con.close()


# ── 注釈コーパス（作品ごとのタブ区切りtxt）→ 読み辞書 ──────────

_LINE_HEAD_RE = re.compile(r'^行番号\s')


def parse_annotation(text: str) -> dict[str, str]:
    """注釈コーパスtxtから読み辞書 {漢字表記: 読み} を作る。

    「読み推定結果:」節の各行（青空文庫の文字列・推定読み・形態素読み・
    音声認識文字列）を集計し、表記ごとに最頻の推定読みを採る。
    漢字を含まない表記・読みが空のものは捨てる。
    """
    votes: dict[str, Counter] = {}
    in_yomi = False
    for line in text.splitlines():
        line = line.strip()
        if not line or _LINE_HEAD_RE.match(line):
            in_yomi = False
            continue
        if line.startswith('「読み推定結果'):
            in_yomi = True
            continue
        if line.startswith('「解析結果'):
            in_yomi = False
            continue
        if not in_yomi:
            continue
        parts = re.split(r'[\t ]+', line)
        if len(parts) < 2:
            continue
        surface, yomi = parts[0], parts[1]
        if surface and yomi and _KANJI_RE.search(surface):
            votes.setdefault(surface, Counter())[yomi] += 1
    return {s: c.most_common(1)[0][0] for s, c in votes.items()}


def apply_readings(text: str, readings: dict[str, str]) -> str:
    """読み辞書をテキストの漢字部分に適用する（長い表記から先に）。

    ルビ由来の読み（すでに仮名になっている部分）はそのまま。
    表記が重なる場合に短い語が長い語を壊さないよう、長い順に置換する。
    """
    if not readings:
        return text
    keys = sorted(readings, key=len, reverse=True)
    pat = re.compile('|'.join(re.escape(k) for k in keys))
    return pat.sub(lambda m: readings[m.group(0)], text)


# ── CLI ───────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        prog='python -m pybunko.ndl',
        description='NDL読みコーパスの書架DBフラグ付け・注釈の確認')
    ap.add_argument('db', help='書架DB（aozora.db）のパス')
    ap.add_argument('--all-works', help='all_works.csv のパス/URL（省略=GitHub raw）')
    a = ap.parse_args(argv)
    n = mark_reading_corpus(a.db, source=a.all_works)
    print(f'読みコーパスあり: {n} 作品にフラグを付けました')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
