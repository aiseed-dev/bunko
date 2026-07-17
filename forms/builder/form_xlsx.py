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

import json
import re
import sys

# 汎用の xlsx 読み書きは pybunko.xlsx（ゼロ依存・他のエクスポートと共通）に集約。
from pybunko.xlsx import read_sheet, write_workbook

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
