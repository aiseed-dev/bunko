# forms — FormRescue（bunko に統合）

WordPress の問い合わせフォームから分離した「受信箱」を軸にしたフォーム機構。
旧 `formrescue/` を bunko に移し、描画は pywashi に一本化した後の姿。

## 構成

| 場所 | 中身 |
|------|------|
| `builder/` | スキーマ編集ツール（`form-builder.html`）と雛形。運用者はここで項目を編集し、`[.form]` に貼る JSON を得る。プレビュー用に `form-render.js` / `form.css` を同梱。 |
| `examples/` | `[.form]` を使った AsciiDoc の例（`お問い合わせ.adoc`）。 |
| `flet/` | 受信箱を取りに行く管理アプリ（プル型・Python/Flet）。 |
| `app/` | 同じ仕様の Flutter 版管理アプリ。 |

## 描画本体は pywashi

フォームの**描画**（`[.form]` ブロック → 対話的フォーム）は pywashi に移設済み。
canonical はこちら：

- `pywashi/src/pywashi/form.py` — markdown-it-py プラグイン（`[.form]` を捕まえる）
- `pywashi/src/pywashi/form_assets/form-render.js` / `form.css` — 描画資産

pywashi で AsciiDoc を組版すると、本文中の `[.form]` が自動でフォームになる。
`builder/` の `form-render.js` / `form.css` は、ビルダー単体プレビュー用の控え
（編集時に効かせるため同梱）。描画の正は pywashi 側。

## Cloudflare Worker は cf-publish へ

受信エンドポイント（`POST /submit` → D1、`GET /items` / `POST /ack`）と
デプロイ道具は `cf-publish/examples/form-worker/` に移した。
