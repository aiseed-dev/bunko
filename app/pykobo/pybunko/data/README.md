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


## kosei_ocr.txt

OCRの読み取りミス・誤入力が生じやすい文字列のチェックリスト（正規表現、439パターン）。
機械チェック（`pybunko.kosei.lint`）の「OCR誤読疑い」で使う。

- **出典**: [青空文庫作業マニュアル【校正編】](https://www.aozora.gr.jp/aozora-manual/index-proofreading.html)
  「5. 正規表現」に点検グループが公開しているリスト（GitHubミラー経由で取得）。
- **ライセンス**: マニュアル本体は CC BY-NC 4.0。本ファイルはそのごく一部
  （事実の列挙に近いチェックリスト）を、出典明記のうえ校正支援という
  マニュアルの目的そのものに使う。営利再配布はしないこと。

## gaiji_jisho.json

外字注記辞書（文字→直し方）の対応表（7,427字）。機械チェック
（`pybunko.kosei`）が、JIS X 0208に無い文字へ「靑→青（包摂適用）」
「この外字注記をコピー: ※［＃…、第3水準…］」と直し方を提示するのに使う。

- **出典**: [青空文庫・外字注記辞書【第八版】](https://www.aozora.gr.jp/gaiji_chuki/)
  （GitHubミラーの `gaiji_chuki/*.html` ＋ 補完として `gaiji_chuki.pdf`）。
  辞書は青空文庫の工作員たちが編んだもの。敬意をもって流用する。
- **生成**: `tools/build_gaiji_jisho.py`（PDF補完に pdftotext を使用）。
  見出し字と置き換え先が同じ（Unicodeでは統合済み）の項は除いてある。
