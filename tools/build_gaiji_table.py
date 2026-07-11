#!/usr/bin/env python3
"""jis2ucs.yml（aozora2html, CC0）→ aozorabunko/data/jis2ucs.json 変換。

開発時に一度だけ実行して、同梱用の素直な JSON を作る。
実行時ロードは標準ライブラリ(json)のみ ── 本体のゼロ依存を守るため、
pyyaml は使わず、flatなYAML（`:面-区-点: "実体参照"`）を正規表現で読む。

出典: aozorahack/aozora2html `yml/jis2ucs.yml`（JIS X 0213:2004 面区点 → Unicode）。
ライセンス: CC0-1.0。値の実体参照は html.unescape で実文字へ復号して格納する
（合成列 例 か゚ = "&#x304B;&#x309A;" は2文字のまま保持）。

    python tools/build_gaiji_table.py [path/to/jis2ucs.yml]
"""
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DATA = HERE.parent / "aozorabunko" / "data"
DEFAULT_SRC = HERE.parent.parent / "_ref" / "aozora2html" / "yml" / "jis2ucs.yml"

# 例:  :1-06-75: "&#x2603;"
_LINE = re.compile(r'^:(?P<key>[12]-\d{2}-\d{2}):\s*"(?P<val>.*)"\s*$')


def build(src: Path, dst: Path) -> int:
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


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SRC
    if not src.exists():
        sys.exit(f"source not found: {src}\n"
                 f"aozora2html を _ref/ に clone してからこのスクリプトを実行してください。")
    dst = PKG_DATA / "jis2ucs.json"
    n = build(src, dst)
    # 検証: 雪だるま 1-06-75 → ☃
    check = json.loads(dst.read_text(encoding="utf-8"))
    assert check.get("1-06-75") == "☃", check.get("1-06-75")
    print(f"wrote {n} entries -> {dst}  (1-06-75 -> {check['1-06-75']!r} OK)")
