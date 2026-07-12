"""kosei.py — 入力・校正支援の機械チェック（青空文庫作業マニュアル準拠）。

公式の作業マニュアル【入力編】【校正編】が定める点検を、ツールとして写す:

  - 文字コード検査 …… 「チェッカー君」相当。JIS X 0201（半角カナ除く）＋
    JIS X 0208 の範囲外の文字を検出する（Python の shift_jis コーデックが
    ちょうど X0201+X0208 なのでこれで判定。cp932 は機種依存文字を含むので不可）。
  - 書式・注記の検査 …… 点検グループが校正編で公開している正規表現
    （ルビの検査・行頭の字下げ・文末の空白・半角記号など）。
  - OCR誤読の検査 …… 校正編の「OCRの読み取りミスや誤入力が生じやすい文字」
    リスト（data/kosei_ocr.txt、出典は data/README.md 参照）。
  - 作業履歴の生成 …… 校正編が求める「どこをどう直したか」ファイル。
    修正前後のテキストから「前 → 後　【誤字】」形式の行を組み立てる。

判定はあくまで「疑い」の提示まで。直すかどうかの最終判断は、底本と
突き合わせる人間の仕事（校正の基本は「原稿尊重」）。
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path

_DATA = Path(__file__).parent / 'data'


@dataclass
class Finding:
    """検査結果の1件。line は1始まり。"""
    line: int
    rule: str
    text: str          # 該当箇所（前後の文脈つき抜粋）
    note: str = ''     # 対処のヒント

    def to_dict(self) -> dict:
        return asdict(self)


# ── 文字コード検査（チェッカー君相当） ──────────────────────────

def charset_errors(text: str) -> list[Finding]:
    """JIS X 0201（半角カナ除く）＋ JIS X 0208 の範囲外の文字を探す。"""
    out: list[Finding] = []
    for ln, line in enumerate(text.splitlines(), 1):
        for ch in dict.fromkeys(line):      # 行内ユニーク
            if ch == '\t':
                out.append(Finding(ln, '文字コード', _clip(line, ch),
                                   'タブ文字は使わない（全角空白で）'))
                continue
            if '｡' <= ch <= 'ﾟ':
                out.append(Finding(ln, '文字コード', _clip(line, ch),
                                   f'半角カナ「{ch}」は使えない（全角に）'))
                continue
            try:
                ch.encode('shift_jis')
            except UnicodeEncodeError:
                name = unicodedata.name(ch, f'U+{ord(ch):04X}')
                out.append(Finding(
                    ln, '文字コード', _clip(line, ch),
                    f'「{ch}」（{name}）は JIS X 0208 に無い'
                    '（包摂適用か外字注記に。外字注記辞書を参照）'))
    return out


# ── 書式・注記の検査（点検グループの正規表現より） ──────────────

# (規則名, パターン, ヒント)。パターンは校正編マニュアル掲載のものを基本に、
# 検査に不向きな広すぎるもの（例: [ヘペベ] 単独）は文脈付きの版のみ採用。
_RULES: list[tuple[str, str, str]] = [
    ('へぺべの混同疑い', r'[ァ-ヶー][へぺべ]|[へぺべ][ァ-ヶー]',
     '片仮名列に接する平仮名へぺべ。片仮名「ヘペベ」の誤読か底本を確認'),
    ('片仮名列中の異字疑い', r'[ァ-ヶー][口工七力二夕卜り一八才][ァ-ヶー]',
     '片仮名の中に漢字・平仮名が一字（口/工/七/力/二/夕/卜/り/一/八/才）'),
    ('平文中の片仮名一字疑い', r'[ぁ-ん][ロエセカニタトリハオ][ぁ-ん]',
     '平仮名の中に片仮名が一字。漢字（口/工/…）の誤読か底本を確認'),
    ('文末の空白', r'[ 　]+$', '行末の不要な空白は削除'),
    ('行頭括弧前の字下げ', r'^　+[（「『【]',
     '行頭に括弧が来る行は字下げしない（マニュアル3-4）'),
    ('ルビに仮名以外', r'《[^《》]*?[^ぁ-んァ-ヶーゞゝヽヾ・／″＼][^《》]*?》',
     'ルビ《》の中は原則かな（学術記号≪≫との混同・入れ子も確認）'),
    ('ルビの過分割疑い', r'《[^》]+》[^ァ-ヶーぁ-ん、。？！―,『』｜「」々]{1,2}《[^》]+》',
     '連続するルビ。複合語なら一つにまとめる（迷ったらまとめる）'),
    ('ルビ拗音の並字疑い',
     r'《[^《》]*?[きぎしじちぢにひびぴみり][やゆよ][^《》]*?》',
     '新かなのルビは拗音を小書き（きょう）。旧かな作品なら並字のまま'),
    ('半角記号', r'[^Ａ-Ｚａ-ｚA-Za-z0-9][!#-&(-+\[-\]|?]',
     '半角の括弧・記号は和文中では使わない（全角に）'),
    ('まれな文字', r'[′．･，－｢♯□｣､]',
     '使われることのまれな文字。誤入力（半角句読点・♯とダッシュ等）を確認'),
    ('マイナス記号のダッシュ疑い', r'－－|[ぁ-んァ-ヶ一-龠]－[ぁ-んァ-ヶ一-龠]',
     'ダッシュは「―」（罫線でもマイナス「－」でもない）。２倍は「――」'),
    ('中点の点線疑い', r'・・+', '底本が「・・」でも中点1つ、「……」は「…」を使う'),
]
_COMPILED = [(name, re.compile(pat), note) for name, pat, note in _RULES]

# ｜の入れ忘れ: 漢字連が3字以上で、ルビがその字数より短い（＝連の一部にしか
# かからないはずなのに「｜」が無い）ものを疑う。邪智暴虐《じゃちぼうぎゃく》の
# ような全体ルビは、読みの方が長くなるので拾わない。
_TATEBO_RE = re.compile(r'(?<!｜)([㐀-鿿豈-鶴々〆〇ヶ]{3,})《([^》]+)》')


def _tatebo_findings(ln: int, line: str) -> list[Finding]:
    return [
        Finding(ln, '｜の入れ忘れ疑い', _clip(line, m.group(0)),
                f'「{m.group(1)}」{len(m.group(1))}字にルビ{len(m.group(2))}字。'
                'かかり始めに「｜」が要るか確認')
        for m in _TATEBO_RE.finditer(line)
        if len(m.group(2)) < len(m.group(1))
    ]


_OCR_RE: re.Pattern | None = None


def _ocr_re() -> re.Pattern:
    global _OCR_RE
    if _OCR_RE is None:
        pats = (_DATA / 'kosei_ocr.txt').read_text(encoding='utf-8').strip()
        _OCR_RE = re.compile(pats)
    return _OCR_RE


def _clip(line: str, around: str, width: int = 14) -> str:
    """行から該当文字列の前後を抜粋。"""
    i = line.find(around)
    if i < 0:
        return line[:width * 2]
    s = max(0, i - width)
    e = min(len(line), i + len(around) + width)
    return ('…' if s else '') + line[s:e] + ('…' if e < len(line) else '')


def lint(text: str, old_style: bool = False) -> list[Finding]:
    """機械チェック一式。old_style=True なら旧字ファイル向け（校閲君相当）も。

    返り値は行番号順の Finding リスト。「疑い」を含むので、
    ヒットした箇所は必ず底本と突き合わせて判断する。
    """
    out = charset_errors(text)
    rules = list(_COMPILED)
    if old_style:
        # 校閲君相当: 旧字ファイルに紛れた新字（校正編掲載の字体対応より）
        shin = ('亜悪圧囲為医壱稲飲隠営栄衛駅円艶塩奥応欧殴穏仮価画会壊懐絵拡殻覚学'
                '岳楽勧巻歓缶観関陥巌顔帰気亀偽戯犠旧拠挙峡挟狭尭暁区駆勲径恵渓経継'
                '茎蛍軽鶏芸欠倹剣圏検権献県険顕験厳効広恒鉱号国済砕斎剤桜冊雑参惨桟'
                '蚕賛残糸歯児辞湿実舎写釈寿収従渋獣縦粛処叙奨将焼称証乗剰壌嬢条浄畳'
                '穣譲醸嘱触寝慎晋真尽図粋酔随髄数枢声静斉摂窃専戦浅潜繊践銭禅双壮捜'
                '挿争総聡荘装騒臓蔵属続堕体対帯滞台滝択沢単担胆団弾断痴遅昼虫鋳庁聴'
                '勅鎮逓鉄転点伝党盗灯当闘独読届縄弐悩脳覇廃拝売麦発髪抜蛮秘浜払仏並'
                '変辺弁舗穂宝褒豊没翻槙万満黙弥薬訳予余与誉揺様謡遥来乱覧竜両猟塁励'
                '礼霊齢恋炉労楼禄亘湾瑶')
        rules.append(('新字の混入疑い', re.compile(f'[{shin}]'),
                      '旧字ファイルに新字。底本がこの字ならそのままに'))
    for ln, line in enumerate(text.splitlines(), 1):
        for name, pat, note in rules:
            for m in pat.finditer(line):
                out.append(Finding(ln, name, _clip(line, m.group(0)), note))
        out += _tatebo_findings(ln, line)
        for m in _ocr_re().finditer(line):
            out.append(Finding(ln, 'OCR誤読疑い', _clip(line, m.group(0)),
                               f'「{m.group(0)}」は誤読・誤入力の頻出形。底本を確認'))
    out.sort(key=lambda f: f.line)
    return out


# ── 作業履歴（校正編2. 「どこをどう直したか」） ──────────────────

def work_history(before: str, after: str, context: int = 8) -> str:
    """修正前後のテキストから、校正編の作業履歴形式のテキストを作る。

        意昧のない抵抗を　→　意味のない抵抗を　【昧】

    行単位で対応を取り、変わった行は文字単位の差分から【誤字】を拾う。
    """
    b_lines = before.replace('\r\n', '\n').split('\n')
    a_lines = after.replace('\r\n', '\n').split('\n')
    sm = SequenceMatcher(None, b_lines, a_lines, autojunk=False)
    entries: list[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        if tag == 'replace' and (i2 - i1) == (j2 - j1):
            for b, a in zip(b_lines[i1:i2], a_lines[j1:j2]):
                entries.append(_history_line(b, a, context))
        elif tag == 'delete':
            entries += [f'{ln}　→　（行を削除）' for ln in b_lines[i1:i2]]
        elif tag == 'insert':
            entries += [f'（行を追加）　→　{ln}' for ln in a_lines[j1:j2]]
        else:
            entries += [f'{b}　→　{a}' for b, a
                        in zip(b_lines[i1:i2], a_lines[j1:j2])]
    if not entries:
        return '修正点はありませんでした。\n'
    return '\n'.join(entries) + '\n'


def _history_line(before: str, after: str, context: int) -> str:
    """1行ぶんの履歴。差分の周辺だけを抜粋し、直した誤字を【】に添える。"""
    cm = SequenceMatcher(None, before, after, autojunk=False)
    ops = [op for op in cm.get_opcodes() if op[0] != 'equal']
    wrong = ''.join(before[i1:i2] for _, i1, i2, _, _ in ops)
    s_b = min((op[1] for op in ops), default=0)
    e_b = max((op[2] for op in ops), default=len(before))
    s_a = min((op[3] for op in ops), default=0)
    e_a = max((op[4] for op in ops), default=len(after))
    b = _window(before, s_b, e_b, context)
    a = _window(after, s_a, e_a, context)
    return f'{b}　→　{a}' + (f'　【{wrong}】' if wrong else '')


def _window(s: str, start: int, end: int, context: int) -> str:
    lo, hi = max(0, start - context), min(len(s), end + context)
    return ('…' if lo else '') + s[lo:hi] + ('…' if hi < len(s) else '')


# ── CLI ───────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        prog='python -m pybunko.kosei',
        description='青空文庫テキストの機械チェック（作業マニュアル準拠）')
    ap.add_argument('input', help='注記テキスト（.txt、Shift_JIS/UTF-8自動判別）')
    ap.add_argument('--old-style', action='store_true',
                    help='旧字ファイル向け（新字の混入も検査）')
    ap.add_argument('--json', action='store_true', help='JSONで出力')
    ap.add_argument('--history', metavar='修正後ファイル',
                    help='inputを修正前として、作業履歴を出力')
    a = ap.parse_args(argv)

    from .convert import read_text
    text = read_text(a.input)
    if a.history:
        print(work_history(text, read_text(a.history)), end='')
        return 0
    findings = lint(text, old_style=a.old_style)
    if a.json:
        print(json.dumps([f.to_dict() for f in findings], ensure_ascii=False,
                         indent=1))
    else:
        for f in findings:
            print(f'{f.line}行 [{f.rule}] {f.text}\n    {f.note}')
        print(f'―― {len(findings)} 件（疑い含む。必ず底本と突き合わせること）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
