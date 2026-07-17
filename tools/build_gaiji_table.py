#!/usr/bin/env python3
"""aozora2html（CC0）の対応表 → aozorabunko/data/*.json 変換（開発時のみ）。

同梱用の素直な JSON を作る。実行時ロードは標準ライブラリ(json)のみで、
本体のゼロ依存を守る。このビルド時スクリプトだけが pyyaml（accent用）を使う。

- jis2ucs.json      … JIS X 0213 面区点 → Unicode（flat YAMLを正規表現で読む）
- accent_table.json … 欧文アクセント分解（base→修飾→[面区点code, 名称]。pyyaml使用）

出典: aozorahack/aozora2html `yml/jis2ucs.yml`, `yml/accent_table.yml`（CC0-1.0）。

    python tools/build_gaiji_table.py [path/to/aozora2html/yml]
"""
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DATA = HERE.parent / "pybunko" / "data"
_CANDIDATE_REFS = [
    HERE.parent / "_ref" / "aozora2html" / "yml",                     # bunko/_ref（将来）
    HERE.parent.parent / "aozora" / "_ref" / "aozora2html" / "yml",   # dev/aozora/_ref（現在地）
    Path("/home/dev/dev/aozora/_ref/aozora2html/yml"),
]
DEFAULT_YML = next((c for c in _CANDIDATE_REFS if c.exists()), _CANDIDATE_REFS[0])

# 例:  :1-06-75: "&#x2603;"
_LINE = re.compile(r'^:(?P<key>[12]-\d{2}-\d{2}):\s*"(?P<val>.*)"\s*$')


def build_gaiji(src: Path, dst: Path) -> int:
    table: dict[str, str] = {}
    for line in src.read_text(encoding="utf-8").splitlines():
        m = _LINE.match(line)
        if not m:
            continue
        table[m["key"]] = html.unescape(m["val"])
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(
        json.dumps(table, ensure_ascii=False, sort_keys=True, indent=0),
        encoding="utf-8",
    )
    return len(table)


def build_accent(src: Path, dst: Path) -> int:
    import yaml  # ビルド時のみの依存
    table = yaml.safe_load(src.read_text(encoding="utf-8"))
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(
        json.dumps(table, ensure_ascii=False, sort_keys=True, indent=0),
        encoding="utf-8",
    )
    return len(table)


if __name__ == "__main__":
    yml = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_YML
    if not (yml / "jis2ucs.yml").exists():
        sys.exit(f"source not found under: {yml}\n"
                 f"aozora2html を _ref/ に clone してからこのスクリプトを実行してください。")

    n = build_gaiji(yml / "jis2ucs.yml", PKG_DATA / "jis2ucs.json")
    g = json.loads((PKG_DATA / "jis2ucs.json").read_text(encoding="utf-8"))
    assert g.get("1-06-75") == "☃", g.get("1-06-75")
    print(f"jis2ucs: {n} entries  (1-06-75 -> {g['1-06-75']!r} OK)")

    m = build_accent(yml / "accent_table.yml", PKG_DATA / "accent_table.json")
    a = json.loads((PKG_DATA / "accent_table.json").read_text(encoding="utf-8"))
    assert a["e"]["'"][0] == "1-09/1-09-63", a["e"]["'"]
    print(f"accent_table: {m} base chars  (e' -> {a['e']["'"][0]} OK)")
