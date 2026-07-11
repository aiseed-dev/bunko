# 同梱データの出典

## jis2ucs.json

JIS X 0213:2004 の面区点（men-ku-ten）→ Unicode 対応表（11,233件）。
外字注記（`※［＃「…」、第3水準1-85-1］`）の解決に使う。

- **出典**: [aozorahack/aozora2html](https://github.com/aozorahack/aozora2html) の `yml/jis2ucs.yml`
- **ライセンス**: CC0-1.0（パブリックドメイン・ディディケーション）。再配布・改変に制限なし。
- **生成**: `tools/build_gaiji_table.py` が上記YAMLを読み、実体参照（`&#x2603;`）を
  実文字（☃）へ復号して JSON 化。合成列（例 `か゚` = か + 半濁点）は複数文字のまま保持。

対応表そのものは aozora2html が JIS X 0213:2004 の公式マッピング
（`vendor/jis2ucs/jisx0213-2004-mono.html`）から生成したもの。敬意をもって流用する。

## accent_table.json

欧文アクセント分解（`〔e'tiquette〕`）の対応表。base文字 → 修飾記号 →
`[面区点code, 名称]` の2〜3段ネスト。面区点は jis2ucs.json 経由で実文字に解決する。

- **出典**: aozora2html の `yml/accent_table.yml`（CC0-1.0）
- **生成**: `tools/build_gaiji_table.py` が YAML をそのまま JSON 化（ビルド時のみ pyyaml 使用）。

