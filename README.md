# 文庫（bunko） — dev.aiseed.bunko

青空文庫の正本（注記付きテキスト）を**構造化Unicodeデータに変換する
Pythonパイプライン（pybunko）**と、それを使う**工作員アプリ「青空工房」
（Flet）**、および生成した**データ資産**。サーバなしで動きます。

> かつて同居していた Flutter 読者アプリ（app/bunko）は廃止しました。
> Webでの閲覧は青空文庫本体があるため、読者向けの独自アプリは持ちません。
> 書架・目次のような一覧は静的サイトが向いています（tools/examples/ に
> 試作、配信は [cf-publish](https://github.com/aiseed-dev/cf-publish) で）。
> コードは git 履歴（〜2026-07-17）から復元できます。

## 何が入っているか

| 場所 | 中身 |
|---|---|
| `app/pykobo/pybunko/` | Python パイプライン ── 正本→Document→JSON/SQLite/EPUB/公式XHTML/フォント資産 |
| `app/pykobo/` | 青空工房（Flet）── 執筆・変換確認・外字チェック・資産づくり |
| `forms/` | FormRescue ── WordPressから分離した問い合わせフォームの受信箱（Flet 管理アプリ・ビルダー） |
| `assets/` | データ資産 ── `aozora.db`（全17,335作品/981作家メタ＋代表27作品の本文）・IPAex明朝（JIS X 0213全外字入り）・`jis2ucs.json`・`cp932.bin` |
| `tools/` | 開発用: `build_assets.py`・`build_gaiji_table.py`・examples/（静的な書架・ビューアの試作） |
| `docs/` | DESIGN・MANUAL・KUMIHAN・LICENSING ほか（正本） |

取得は GitHub ミラー（raw.githubusercontent.com）のみ・必ずキャッシュ経由。
公式サーバー（aozora.gr.jp）には一切アクセスしません。

## 使い方

```bash
pip install -e './app/pykobo[epub]'   # import pybunko（ローカル専用・PyPI未登録）
cd app/pykobo && flet run             # 青空工房（デスクトップ）
KOBO_PORT=8789 python main.py         # 同・Webサーバ（LANのスマフォからも）
pytest app/pykobo/tests               # 138テスト・完全オフライン
```

データ資産の再生成:

```bash
python tools/build_assets.py
```

全体設計は [docs/DESIGN.md](docs/DESIGN.md)、パイプラインの使い方・拡張の仕方は
[docs/MANUAL.md](docs/MANUAL.md)、注記→変換の対応は
[docs/KUMIHAN.md](docs/KUMIHAN.md)（本家「組版案内」の現代版）。

## アーキテクチャ

- 一次表現は「外字解決済みの構造化Unicodeデータ」（`Document`、
  `parser.py` が唯一のパーサ）。出力形式は `formats.py` に関数を足す。
- pybunko 本体はゼロ依存（標準ライブラリのみ）。EPUB・組版・フォント等の
  重い依存は extras（`[epub]`/`[washi]`/`[font]`…）。
- 縦書き・原稿用紙・PDF組版は [pywashi](https://github.com/aiseed-dev/pywashi)、
  AsciiDoc は [pyasciidoc](https://github.com/aiseed-dev/pyasciidoc) に委譲。

## ライセンス

コードは **AGPL-3.0-or-later**（Copyright (C) 2026 aiseed.dev）。データは **CC BY 4.0 基本**（出典: 青空文庫）。
詳細・例外（CC0対応表・IPAexフォント等）は [docs/LICENSING.md](docs/LICENSING.md)。
外字対応表は aozora2html 由来（CC0）。図書カードのメタデータは CC BY 4.0（青空文庫）。
収録ファイルの利用は「青空文庫収録ファイルの取り扱い規準」に従ってください。
