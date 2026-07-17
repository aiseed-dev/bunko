#!/usr/bin/env python3
"""form_xlsx.py — フォーム定義を表計算(xlsx)で作る/編集する（標準ライブラリのみ）。

運用者は表計算(OnlyOffice / Excel / LibreOffice)で項目を1行ずつ並べ、
それを `[.form]` に貼る JSON へ変換する。項目の追加・並べ替え・選択肢の
編集は、表の方が form-builder.html より速く・共同編集しやすい。

xlsx は zip+XML なので、依存を足さず zipfile と xml だけで読み書きする
（bunko の「道具は軽く」方針。openpyxl は使わない）。

使い方:
  python form_xlsx.py --template form.xlsx      # 雛形の表を作る
  python form_xlsx.py form.xlsx > form.json     # 表 → フォーム定義JSON
  python form_xlsx.py form.json -o form.xlsx    # フォーム定義JSON → 表(往復)

表の構成:
  シート「項目」  … 1行1項目。列: 項目名 / ラベル / 種別 / 必須 / 選択肢 /
                    プレースホルダ / 初期値 / 一致確認 / 書式
  シート「設定」  … key/value 2列。action / sitekey / confirm / intro
                    （無ければ雛形の既定値を使う）
"""
from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from xml.sax.saxutils import escape

_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

# フィールドのキー ↔ 表の日本語見出し。読み込みは英語キー・日本語見出しの
# どちらの列名でも受ける（正規化して突き合わせる）。
FIELD_COLUMNS = [
    ("name", "項目名"),
    ("label", "ラベル"),
    ("type", "種別"),
    ("required", "必須"),
    ("options", "選択肢"),
    ("placeholder", "プレースホルダ"),
    ("default", "初期値"),
    ("match", "一致確認"),
    ("format", "書式"),
]
_HEADER_TO_KEY = {}
for _k, _jp in FIELD_COLUMNS:
    _HEADER_TO_KEY[_k.lower()] = _k
    _HEADER_TO_KEY[_jp] = _k

_SETTING_KEYS = ("action", "sitekey", "confirm", "intro")
_TRUE_WORDS = {"true", "1", "yes", "○", "◯", "はい", "必須", "y", "t", "✓"}
_LIST_SPLIT = re.compile(r"[\n,、，]+")

_TEMPLATE_SETTINGS = {
    "action": "https://<WORKER>/submit",
    "sitekey": "0xSITEKEY",
    "confirm": "true",
}
_TEMPLATE_FIELDS = [
    {"name": "your-name", "label": "お名前", "type": "text", "required": True,
     "placeholder": "例)山田 太郎"},
    {"name": "your-email", "label": "メールアドレス", "type": "email",
     "required": True, "placeholder": "例)sample@example.com"},
    {"name": "your-email2", "label": "メールアドレス(確認)", "type": "email",
     "required": True, "match": "your-email"},
    {"name": "tel", "label": "電話番号", "type": "tel", "format": "tel"},
    {"name": "category", "label": "お問い合わせ種別", "type": "select",
     "required": True, "options": ["サービスについて", "お見積り", "その他"]},
    {"name": "your-message", "label": "お問い合わせ内容", "type": "textarea",
     "required": True},
]


# ── 汎用 xlsx リーダー（他のエクスポートでも再利用できる最小実装）─────────

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _col_index(ref: str) -> int:
    """セル参照 'AB12' → 0始まりの列番号。"""
    letters = re.match(r"[A-Z]+", ref)
    n = 0
    for ch in letters.group(0):
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _shared_strings(zf: zipfile.ZipFile) -> list[str]:
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    out = []
    for si in root:
        out.append("".join(t.text or "" for t in si.iter() if _local(t.tag) == "t"))
    return out


def _sheet_paths(zf: zipfile.ZipFile) -> "dict[str, str]":
    """シート名 → worksheet の zip 内パス。"""
    import xml.etree.ElementTree as ET
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rid_to_target = {r.get("Id"): r.get("Target") for r in rels}
    out = {}
    for s in wb.iter():
        if _local(s.tag) == "sheet":
            rid = s.get(f"{{{_R_NS}}}id")
            target = rid_to_target.get(rid, "")
            if not target.startswith("/"):
                target = "xl/" + target.lstrip("/")
            out[s.get("name")] = target.lstrip("/")
    return out


def read_sheet(data: bytes, sheet: str | None = None) -> "list[list[str]]":
    """xlsx の1シートを行×列の文字列テーブルとして読む。"""
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        strings = _shared_strings(zf)
        paths = _sheet_paths(zf)
        if sheet is None:
            path = next(iter(paths.values()))
        elif sheet in paths:
            path = paths[sheet]
        else:
            return []
        root = ET.fromstring(zf.read(path))
    rows = []
    for row in root.iter():
        if _local(row.tag) != "row":
            continue
        cells = {}
        for c in row:
            if _local(c.tag) != "c":
                continue
            ref = c.get("r") or "A1"
            ctype = c.get("t")
            text = ""
            if ctype == "inlineStr":
                text = "".join(t.text or "" for t in c.iter()
                               if _local(t.tag) == "t")
            else:
                v = next((e for e in c if _local(e.tag) == "v"), None)
                if v is not None and v.text is not None:
                    text = strings[int(v.text)] if ctype == "s" else v.text
            cells[_col_index(ref)] = text
        width = max(cells) + 1 if cells else 0
        rows.append([cells.get(i, "") for i in range(width)])
    return rows


# ── 汎用 xlsx ライター（inlineStr のみ・sharedStrings 不要の最小実装）──────

_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
    "{sheets}</Types>"
)
_ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
    "</Relationships>"
)
_STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<styleSheet xmlns="{_NS}">'
    '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
    '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
    '<borders count="1"><border/></borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
    '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
    "</styleSheet>"
)


def _col_letter(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _sheet_xml(rows: "list[list]") -> str:
    out = [f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="{_NS}"><sheetData>']
    for ri, row in enumerate(rows, 1):
        out.append(f'<row r="{ri}">')
        for ci, val in enumerate(row):
            if val is None or val == "":
                continue
            ref = f"{_col_letter(ci)}{ri}"
            txt = escape(str(val))
            out.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{txt}</t></is></c>')
        out.append("</row>")
    out.append("</sheetData></worksheet>")
    return "".join(out)


def write_workbook(sheets: "dict[str, list[list]]") -> bytes:
    """{シート名: 行のリスト} → xlsx バイト列。"""
    names = list(sheets)
    ct_over = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, len(names) + 1))
    wb_sheets = "".join(
        f'<sheet name="{escape(n)}" sheetId="{i}" r:id="rId{i}"/>'
        for i, n in enumerate(names, 1))
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{_NS}" xmlns:r="{_R_NS}"><sheets>{wb_sheets}</sheets></workbook>')
    rel_items = "".join(
        f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
        for i in range(1, len(names) + 1))
    styles_rid = len(names) + 1
    rel_items += (f'<Relationship Id="rId{styles_rid}" '
                  'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
                  'Target="styles.xml"/>')
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{rel_items}</Relationships>")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES.format(sheets=ct_over))
        zf.writestr("_rels/.rels", _ROOT_RELS)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        zf.writestr("xl/styles.xml", _STYLES)
        for i, name in enumerate(names, 1):
            zf.writestr(f"xl/worksheets/sheet{i}.xml", _sheet_xml(sheets[name]))
    return buf.getvalue()


# ── フォーム定義 ⇄ 表 の対応付け ─────────────────────────────────────────

def _norm_bool(s: str) -> bool:
    return s.strip().lower() in _TRUE_WORDS


def from_xlsx(data: bytes) -> dict:
    """表(xlsx) → フォーム定義 dict。"""
    # 設定（無ければ雛形の既定）
    settings = dict(_TEMPLATE_SETTINGS)
    for row in read_sheet(data, "設定"):
        if len(row) >= 2 and row[0].strip() in _SETTING_KEYS:
            settings[row[0].strip()] = row[1].strip()

    rows = read_sheet(data, "項目") or read_sheet(data)
    if not rows:
        raise ValueError("項目シートが空です")
    # 見出し行 → 列インデックス（英語キー/日本語見出しどちらでも可）
    header = rows[0]
    col_key = {}
    for i, h in enumerate(header):
        key = _HEADER_TO_KEY.get(h.strip().lower()) or _HEADER_TO_KEY.get(h.strip())
        if key:
            col_key[key] = i
    if "name" not in col_key or "type" not in col_key:
        raise ValueError("見出し行に「項目名(name)」と「種別(type)」が必要です")

    fields = []
    for row in rows[1:]:
        def cell(k: str) -> str:
            i = col_key.get(k)
            return row[i].strip() if i is not None and i < len(row) else ""
        name = cell("name")
        if not name:
            continue  # 空行は飛ばす
        f: dict = {"name": name, "label": cell("label") or name,
                   "type": cell("type") or "text"}
        if _norm_bool(cell("required")):
            f["required"] = True
        for k in ("placeholder", "default", "match", "format"):
            v = cell(k)
            if v:
                f[k] = v
        opts = cell("options")
        if opts:
            f["options"] = [o.strip() for o in _LIST_SPLIT.split(opts) if o.strip()]
        fields.append(f)
    if not fields:
        raise ValueError("項目が1つもありません")

    schema: dict = {"action": settings.get("action", ""),
                    "sitekey": settings.get("sitekey", "")}
    if _norm_bool(settings.get("confirm", "true")):
        schema["confirm"] = True
    if settings.get("intro"):
        schema["intro"] = settings["intro"]
    schema["fields"] = fields
    return schema


def to_xlsx(schema: dict) -> bytes:
    """フォーム定義 dict → 表(xlsx)。項目シート＋設定シート。"""
    header = [jp for _, jp in FIELD_COLUMNS]
    rows = [header]
    for f in schema.get("fields", []):
        row = []
        for key, _jp in FIELD_COLUMNS:
            v = f.get(key, "")
            if key == "required":
                v = "○" if f.get("required") else ""
            elif key == "options" and isinstance(v, list):
                v = "、".join(v)
            row.append(v)
        rows.append(row)

    settings_rows = [["key", "value"]]
    for k in _SETTING_KEYS:
        if k == "confirm":
            settings_rows.append([k, "true" if schema.get("confirm") else "false"])
        elif k in schema:
            settings_rows.append([k, schema[k]])
        elif k in _TEMPLATE_SETTINGS:
            settings_rows.append([k, _TEMPLATE_SETTINGS[k]])
    return write_workbook({"項目": rows, "設定": settings_rows})


def template() -> bytes:
    """記入例入りの雛形 xlsx。"""
    return to_xlsx({**{"confirm": True}, **_TEMPLATE_SETTINGS,
                    "fields": _TEMPLATE_FIELDS})


def _main(argv: "list[str]") -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="form_xlsx", description=__doc__.split("\n")[0])
    ap.add_argument("input", nargs="?", help="入力 (.xlsx → JSON / .json → xlsx)")
    ap.add_argument("-o", "--output", help="出力先（省略時は標準出力/推定名）")
    ap.add_argument("--template", metavar="OUT.xlsx",
                    help="記入例入りの雛形xlsxを書き出して終了")
    args = ap.parse_args(argv)

    if args.template:
        with open(args.template, "wb") as fh:
            fh.write(template())
        print(f"雛形を書き出しました: {args.template}", file=sys.stderr)
        return 0
    if not args.input:
        ap.error("input か --template を指定してください")

    if args.input.endswith(".xlsx"):
        schema = from_xlsx(open(args.input, "rb").read())
        text = json.dumps(schema, ensure_ascii=False, indent=2)
        if args.output:
            open(args.output, "w", encoding="utf-8").write(text + "\n")
        else:
            print(text)
    else:  # JSON → xlsx
        schema = json.loads(open(args.input, encoding="utf-8").read())
        out = args.output or (args.input.rsplit(".", 1)[0] + ".xlsx")
        with open(out, "wb") as fh:
            fh.write(to_xlsx(schema))
        print(f"表を書き出しました: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
