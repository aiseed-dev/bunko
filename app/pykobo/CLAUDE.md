# CLAUDE.md ── app/pykobo（青空工房＋pybunko）の作業規約

## これは何か

bunkoモノレポのPython側。**青空工房**（Flet工作員アプリ・検査/資産/検証の3タブ）と、
その内部実装 **pybunko**（正本→Unicode Document→JSON/SQLite/EPUB/公式XHTML/フォント資産）。
全体設計は ../../docs/DESIGN.md、使い方と拡張の仕方は ../../docs/MANUAL.md（正本）。

## アーキテクチャ（pybunko・変更時は事前相談）

```
catalog.py / card.py / db.py   → Library・Work・図書カード・SQLite（メタ＋doc/card JSON列）
parser.py                      → 注記付きテキスト → Document（唯一の中間表現）
formats.py / corpus.py / convert.py → 出力形式（HTML/EPUB/TTS/MD/JSON/Parquet）
official.py / fonts.py         → 公式XHTML再現（凍結維持）／外字フォント資産
data/                          → CC0対応表（再生成は ../../tools/build_gaiji_table.py）
```

## 絶対規則

1. 公式サーバー（aozora.gr.jp）にアクセスしない。取得はGitHubミラー
   `raw.githubusercontent.com/aozorabunko/aozorabunko/master/` のみ・必ずキャッシュ経由。
2. pybunko本体はゼロ依存（標準ライブラリのみ）。重い依存は extras（epub/washi/parquet/font）。
3. 著作権存続作品はデフォルト除外（public_domain_only=True）。
4. Document が唯一の中間表現。出力形式は formats に関数を足す。
5. **PyPIには個別登録しない**（ローカル編集インストール専用: `pip install -e '.[epub]'`）。
6. **GitHubへのpush等の公開操作はユーザー自身が実行**（コマンド提示まで）。
7. Fletで重い処理は必ず `page.run_thread()`（UIスレッドで回すとWebSocketが切れて完走しない）。

## テスト

```bash
pip install -e '.[epub]' pytest && pytest     # 98件・完全オフライン（urlopen遮断）
```

- 回帰の基準作品: 走れメロス（同梱fixture）・吾輩は猫である（外字35）・山月記（外字22）
- 新しい注記対応は、_ref/aozora2html（Ruby, CC0）のテストを意味構造ファーストで
  pytest に翻訳してから実装（詳細: MANUAL §5.1）

## 工房の起動

```bash
flet run aozora_kobo.py                  # デスクトップ
KOBO_PORT=8789 python aozora_kobo.py     # Webサーバ
```

## ライセンス

コードは AGPL-3.0-or-later、データは CC BY 4.0 基本（../../docs/LICENSING.md）。
