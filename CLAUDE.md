# CLAUDE.md ── bunko（青空文庫: pybunko＋データ資産）の作業規約

## これは何か

青空文庫の正本（注記付きテキスト）を扱う独立リポジトリ。中身は
**pybunko**（正本→Unicode Document→JSON/SQLite/EPUB/公式XHTML/フォント資産）
と、生成した**データ資産**（assets/）、開発スクリプト（tools/）、設計文書
（docs/ が正本）。運用（資産の再生成・ミラー取得・書架データの維持）を担う。

エディタ（AISeed工房）は [pykobo](https://github.com/aiseed-dev/pykobo) に
独立した（2026-07-18）。pykobo は pybunko をここから参照する。

## アーキテクチャ（変更時は事前相談）

```
pybunko/
  catalog.py / card.py / db.py   → Library・Work・図書カード・SQLite（メタ＋doc/card JSON列）
  parser.py                      → 注記付きテキスト → Document（唯一の中間表現）
  formats.py / corpus.py / convert.py → 出力形式（HTML/EPUB/TTS/MD/JSON/Parquet）
  official.py / fonts.py         → 公式XHTML再現（凍結維持）／外字フォント資産
  xlsx.py                        → 表計算(xlsx)の最小I/O（stdlibのみ）
  data/                          → CC0対応表（再生成は tools/build_gaiji_table.py）
```

## 絶対規則

1. 公式サーバー（aozora.gr.jp）にアクセスしない。取得はGitHubミラー
   `raw.githubusercontent.com/aozorabunko/aozorabunko/master/` のみ・必ずキャッシュ経由。
2. pybunko本体はゼロ依存（標準ライブラリのみ）。重い依存は extras（epub/washi/parquet/font）。
3. 著作権存続作品はデフォルト除外（public_domain_only=True）。
4. Document が唯一の中間表現。出力形式は formats に関数を足す。
5. **PyPIには登録しない**。利用は `pip install -e '.[epub]'` か
   git 指定（`pybunko @ git+https://github.com/aiseed-dev/bunko.git`）。
6. **GitHubへのpush等の公開操作はユーザー自身が実行**（コマンド提示まで）。

## テスト

```bash
pip install -e '.[epub]' pytest && pytest tests   # 完全オフライン（urlopen遮断）
```

- 回帰の基準作品: 走れメロス（同梱fixture）・吾輩は猫である（外字35）・山月記（外字22）
- 新しい注記対応は、_ref/aozora2html（Ruby, CC0）のテストを意味構造ファーストで
  pytest に翻訳してから実装（詳細: docs/MANUAL.md §5.1）

## データ資産の再生成

```bash
python tools/build_assets.py     # assets/（aozora.db・外字表・cp932.bin・フォント）
```

## ライセンス

コードは AGPL-3.0-or-later、データは CC BY 4.0 基本（docs/LICENSING.md）。
