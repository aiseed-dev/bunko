"""card.py — 図書カード（cardNNNN.html）から詳細メタデータを取り込む

図書カードには、カタログCSVに無い詳細がある: 底本（出版社・初版発行日・校正に使用）、
入力者・校正者（工作員）、作家の生没年、NDC分類、ファイル一覧（初登録日・更新日）など。
これを構造化して dict にする。方針どおり「細部は JSON のまま」── SQLite には
works.card 列としてそのまま載せる（db.py）。

カードのメタデータは CC BY 4.0（青空文庫）。取得はミラー経由・キャッシュ必須。

    from pybunko import Library
    card = Library().search('走れメロス')[0].card()
    card['staff']          # {'入力': '金川一之', '校正': '高橋美奈子'}
    card['books'][0]       # {'role': '底本', '名称': '太宰治全集3', '出版社': …}
"""
from __future__ import annotations

import re

# tr 行 → セル列。カードは機械生成のHTMLなので正規表現で安定して読める
_TR_RE = re.compile(r'<tr[^>]*>(.*?)</tr>', re.S)
_CELL_RE = re.compile(r'<t[hd][^>]*>(.*?)</t[hd]>', re.S)
_TAG_RE = re.compile(r'<[^>]+>')
_H2_RE = re.compile(r'<h2[^>]*>(.*?)</h2>', re.S)

# 底本データ内でグループの先頭になる見出し
_BOOK_HEADS = ('底本', '底本の親本')


def _strip(cell: str) -> str:
    return _TAG_RE.sub('', cell).replace('&nbsp;', ' ').strip()


def _rows(section_html: str) -> list[list[str]]:
    out = []
    for tr in _TR_RE.finditer(section_html):
        cells = [_strip(c) for c in _CELL_RE.findall(tr.group(1))]
        cells = [c.rstrip('：:') for c in cells]
        if any(cells):
            out.append(cells)
    return out


def _pairs(rows: list[list[str]]) -> list[tuple[str, str]]:
    """[見出し, 値] 形式の行 → (key, value) ペア列（値なし行はスキップ）。"""
    return [(r[0], r[1]) for r in rows if len(r) >= 2 and r[0]]


def _group(pairs: list[tuple[str, str]], heads: tuple[str, ...],
           head_key: str) -> list[dict]:
    """先頭キー（heads）が現れるたびに新しいグループを始める。"""
    groups: list[dict] = []
    for k, v in pairs:
        if k in heads:
            groups.append({'role': k, head_key: v})
        elif groups:
            groups[-1][k] = v
    return groups


def parse_card(html: str) -> dict:
    """図書カードHTML → 構造化 dict（work/authors/books/staff/files）。"""
    # セクションで分割（h2見出し → 次のh2まで）
    marks = [(m.start(), _strip(m.group(1))) for m in _H2_RE.finditer(html)]
    sections: dict[str, str] = {}
    for i, (pos, name) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(html)
        sections[name] = html[pos:end]

    card: dict = {}
    # カード冒頭（最初のh2より前）のタイトル表: 作品名・作品名読み・著者名 が入る
    head_html = html[:marks[0][0]] if marks else html
    card['work'] = dict(_pairs(_rows(head_html)))
    if '作品データ' in sections:
        card['work'].update(dict(_pairs(_rows(sections['作品データ']))))
    if '作家データ' in sections:
        card['authors'] = _group(_pairs(_rows(sections['作家データ'])),
                                 ('分類',), 'role_value') or []
        # 分類（著者/翻訳者…）は role_value に入るので整える
        for a in card['authors']:
            a['分類'] = a.pop('role_value', '')
            a.pop('role', None)
    if '底本データ' in sections:
        card['books'] = _group(_pairs(_rows(sections['底本データ'])),
                               _BOOK_HEADS, '名称')
    if '工作員データ' in sections:
        card['staff'] = dict(_pairs(_rows(sections['工作員データ'])))
    if 'ファイルのダウンロード' in sections:
        rows = _rows(sections['ファイルのダウンロード'])
        if rows and len(rows[0]) >= 3:
            header, files = rows[0], []
            for r in rows[1:]:
                if len(r) >= 3:
                    files.append({h: v for h, v in zip(header, r) if v})
            card['files'] = files
    return card


def decode_card(data: bytes) -> str:
    """カードHTMLの復号。ミラーはUTF-8、公式系の生成物はShift_JISのことがある。"""
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        return data.decode('shift_jis', errors='replace')
