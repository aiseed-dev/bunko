# 文庫（bunko） — dev.aiseed.bunko

青空文庫を第一の蔵書とする、**サーバなし・オフライン**の読書アプリ（Flutter）。
Web / Linux / Android / iOS / デスクトップに同一コードで出せます。

## 何が入っているか

同梱するのは**データ資産2つ**だけ。実行時にPythonは要りません。

| 資産 | 内容 |
|---|---|
| `assets/aozora.db` | 書架メタ全17,335作品/981作家（SQLite）＋代表27作品の本文・図書カード（JSON列） |
| `assets/fonts/ipaexm.ttf` | IPAex明朝 — 本文＋**JIS X 0213全外字**を1フォントで（外字は実Unicode文字で描く） |

補助: `assets/jis2ucs.json`（外字面区点→Unicode, CC0）、`assets/cp932.bin`（Shift_JIS復号表）。

## 画面

1. **書架** — 五十音行タブ・検索（SQLiteメタを引くだけ）
2. **図書カード** — 底本・初出・入力者/校正者・作家生没年（card列JSON。未取得はミラーから）
3. **読書** — ルビ・傍点・見出し・字下げ。**横書き／縦書き切替**・文字サイズ変更

未取得の本文は GitHubミラー（raw.githubusercontent.com）から取得し、
**Dart内で Shift_JIS復号→注記パース→doc列に保存**（次回からオフライン）。
公式サーバー（aozora.gr.jp）には一切アクセスしません。

## リポジトリ構成（アプリ＋資産パイプライン）

```
bunko/
├── app/
│   ├── bunko/                # Flutter 読者アプリ本体（lib/ web/ linux/ test/）
│   └── kobo/                 # 青空工房 ── Flet 工作員ツール（検査・資産・検証）
│       ├── assets -> ../../assets   # symlink（共有資産を参照）
│       └── （tool は tools/ へ移動）
├── packages/
│   └── pybunko/              # PyPI: pybunko ── 正本→Unicode Document→JSON/SQLite/EPUB/
│                             #   公式XHTML(official)・外字フォント資産(fonts) まで一体
├── assets/                   # 共有データ資産（aozora.db・IPAex明朝・jis2ucs.json・cp932.bin）
├── tools/                    # 開発用: build_assets.py・build_gaiji_table.py・examples/
└── docs/                     # 設計書（DESIGN.md）・マニュアル（MANUAL.md）の正本
```

`pip install -e './app/kobo[epub]'` で `import pybunko`（ローカル専用・PyPIには個別登録しない）。
全体設計は [docs/DESIGN.md](docs/DESIGN.md)、パイプラインの使い方・拡張の仕方は [docs/MANUAL.md](docs/MANUAL.md)。

## アーキテクチャ

設計の正本は [docs/DESIGN.md](docs/DESIGN.md)。役割分担: **読者アプリ=Flutter（これ）／工作員ツール=Flet**。

- 一次表現は「外字解決済みの構造化Unicodeデータ」（Document JSON）。
  `lib/data/models.dart` は Python 版 `Document.to_dict()` と**スキーマ往復互換**。
- `lib/data/aozora_parser.dart` — 注記パーサのDart移植（ルビ・外字・見出し・字下げ・装飾・挿絵）
- `lib/data/db.dart` — SQLite（io=ファイル / web=wasm を条件付きインポートで切替）
- `lib/ui/vertical_reader.dart` — 縦書き自前レイアウト（列送り右→左・ルビ右添え・括弧回転・句読点寄せ）

## ビルド

```bash
cd app/bunko
flutter test                 # 13 tests
flutter build web --release  # web/sqlite3.wasm 同梱済み
flutter build linux --release
```

データ資産の再生成（Python環境・aozorabunko が必要）:

```bash
python tools/build_assets.py
```

## ライセンス

コードはMIT。IPAexフォントは IPA Font License 1.0（assets/fonts/ 参照）。
外字対応表は aozora2html 由来（CC0）。図書カードのメタデータは CC BY 4.0（青空文庫）。
収録ファイルの利用は「青空文庫収録ファイルの取り扱い規準」に従ってください。
