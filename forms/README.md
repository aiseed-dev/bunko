# forms — FormRescue（bunko に統合）

WordPress の問い合わせフォームから分離した「受信箱」を軸にしたフォーム機構。
旧 `formrescue/` を bunko に移し、描画は pywashi に一本化した後の姿。

## 構成

| 場所 | 中身 |
|------|------|
| `builder/` | スキーマ編集ツール。運用者はここで項目を編集し、`[.form]` に貼る JSON を得る。ブラウザの `form-builder.html`、または表計算で作る `form_xlsx.py`（下記）。プレビュー用に `form-render.js` / `form.css` を同梱。 |
| `examples/` | `[.form]` を使った AsciiDoc の例（`お問い合わせ.adoc`）。 |
| `flet/` | 受信箱を取りに行く管理アプリ（プル型・Python/Flet）。 |

Flutter 版管理アプリ（`app/`）は廃止（2026-07-17。Flet 版に一本化。git 履歴から復元可）。

## 表計算でフォームを作る（`builder/form_xlsx.py`）

項目は「1行1項目」なので、表計算の方が速く・共同編集しやすい。運用者は
OnlyOffice / Excel / LibreOffice で列を埋め、それを `[.form]` の JSON にする。
標準ライブラリだけの変換（依存なし・openpyxl 不要）。

```bash
python builder/form_xlsx.py --template form.xlsx   # 記入例入りの雛形を作る
# → 表計算で「項目」シートを編集（項目名/ラベル/種別/必須/選択肢/…）
python builder/form_xlsx.py form.xlsx > form.json  # 表 → [.form] に貼る JSON
python builder/form_xlsx.py form.json -o form.xlsx # JSON → 表（往復・既存フォームの編集）
```

「項目」シートの見出しは日本語（項目名/ラベル/種別/必須/選択肢/プレースホルダ/
初期値/一致確認/書式）でも英語キー（name/label/type/…）でも可。選択肢は
セル内で改行・読点・カンマ区切り。必須は ○/はい/true 等。`action`/`sitekey`/
`confirm` は「設定」シートで（省略時は雛形の既定値）。

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
