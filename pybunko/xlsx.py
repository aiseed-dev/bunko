"""xlsx.py — 表計算(xlsx)の最小読み書き（標準ライブラリのみ・ゼロ依存）。

xlsx は zip+XML なので、依存を足さずに読み書きできる（bunko の方針）。
汎用の read_sheet / write_workbook と、表 → Markdown/AsciiDoc 表への変換。
フォーム定義(forms/builder/form_xlsx.py)・書架カタログ・点検結果・受信箱
など、表で出し入れしたいものすべての土台。

    from pybunko import xlsx
    rows = xlsx.read_sheet(open('x.xlsx','rb').read())        # 1シート → 行×列
    data = xlsx.write_workbook({'Sheet1': [['a','b'],[1,2]]}) # 行 → xlsx bytes
    md   = xlsx.to_markdown_table(rows)                        # 表 → Markdown表
"""
from __future__ import annotations

import io
import re
import zipfile
from xml.sax.saxutils import escape

_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


# ── リーダー ─────────────────────────────────────────────────────────────

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _col_index(ref: str) -> int:
    """セル参照 'AB12' → 0始まりの列番号。"""
    letters = re.match(r"[A-Z]+", ref)
    n = 0
    for ch in letters.group(0):
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _shared_strings(zf: zipfile.ZipFile) -> "list[str]":
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


def read_sheet(data: bytes, sheet: "str | None" = None) -> "list[list[str]]":
    """xlsx の1シートを行×列の文字列テーブルとして読む（先頭シート既定）。"""
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        strings = _shared_strings(zf)
        paths = _sheet_paths(zf)
        if not paths:
            return []
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


def sheet_names(data: bytes) -> "list[str]":
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return list(_sheet_paths(zf))


# ── ライター（inlineStr のみ・sharedStrings 不要の最小実装）────────────────

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


# ── 表 → Markdown / AsciiDoc 表 ─────────────────────────────────────────

def _trim(rows: "list[list[str]]") -> "list[list[str]]":
    """末尾の空行、および全行を通じて空の右端列を落とす。"""
    rows = [r for r in rows if any((c or "").strip() for c in r)]
    if not rows:
        return []
    width = max(len(r) for r in rows)
    rows = [list(r) + [""] * (width - len(r)) for r in rows]
    while width > 1 and all(not (r[width - 1] or "").strip() for r in rows):
        width -= 1
        rows = [r[:width] for r in rows]
    return rows


def to_markdown_table(rows: "list[list[str]]", header: bool = True) -> str:
    """行×列 → GFM の Markdown 表。1行目を見出しにする（header=True）。"""
    rows = _trim(rows)
    if not rows:
        return ""
    def cell(x: str) -> str:
        return str(x).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").strip()
    width = len(rows[0])
    out = []
    body = rows
    if header:
        out.append("| " + " | ".join(cell(c) for c in rows[0]) + " |")
        out.append("| " + " | ".join(["---"] * width) + " |")
        body = rows[1:]
    for r in body:
        out.append("| " + " | ".join(cell(c) for c in r) + " |")
    return "\n".join(out) + "\n"


def to_asciidoc_table(rows: "list[list[str]]", header: bool = True) -> str:
    """行×列 → AsciiDoc の表（|=== 区切り）。header=True で見出し行つき。"""
    rows = _trim(rows)
    if not rows:
        return ""
    def cell(x: str) -> str:
        return str(x).replace("|", "\\|").replace("\n", " ").strip()
    out = []
    if header:
        out.append('[options="header"]')
    out.append("|===")
    for r in rows:
        out.append(" ".join(f"|{cell(c)}" for c in r))
    out.append("|===")
    return "\n".join(out) + "\n"
