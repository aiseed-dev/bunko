# FormRescue (Flet)

WordPressの問い合わせフォームから分離した受信箱(Cloudflare Worker + D1、または
自社サーバー)を、ローカル端末に取りに行く(プル型)ための管理アプリ。
[Flutter版](../app)と同じ仕様の実装(Python / Flet)。

仕様の全文は [`website/docs/plan/wordpress/todo.md`](../../../website/docs/plan/wordpress/todo.md)
の「管理アプリの仕様」を参照。

## 開発環境

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e .   # または pip install flet[all] httpx flet-camera pyzbar Pillow
```

Flet 1.0(0.85系)の宣言的スタイル(`@ft.component` + `use_state`/`use_effect`/`use_ref`)
で書かれている。状態管理ライブラリは使わず、画面遷移も専用ライブラリではなく
`main.py` の `App` コンポーネント内の `use_state` だけで行っている(画面数が
3つだけの小さいアプリのため)。

## 初回設定

`deploy.py`(または `cf-publish`)が発行するQRコードの中身は次のJSON形式:

```json
{"url": "https://xxxx.workers.dev", "token": "xxxxxxxx..."}
```

QRカメラ読み取りは Android / iOS のみ対応。`flet-camera` パッケージ自体が
デスクトップ(Linux/Windows/macOS)向けのプレビューを提供していないため、
それ以外の環境では手入力欄のみが表示される([settings_view.py](settings_view.py)
の `qr_scan_supported()` で判定)。

QR読み取りは `flet-camera` でカメラプレビュー+静止画撮影を行い、`pyzbar` +
`Pillow` でその画像からQRコードをデコードする。3つとも pypi.flet.dev に
Android/iOS向けのプリビルドwheelがあることを確認済み(`pip index versions`
で個別に確認したうえで採用)。ただし、この開発環境にはAndroid実機がなく、
QRスキャン自体の実機動作は未検証(手入力によるURL/TOKEN設定は動作確認済み)。

## データの保存場所

- SQLite: `ft.StoragePaths().get_application_documents_directory()` 配下の
  `data/inbox.db`(OS標準のアプリドキュメント領域。Flutter版の `path_provider`
  に相当)
- バックアップ: 同領域の `backups/inbox-YYYYMMDD.db`。起動時に1日1回作成し、
  直近30日分を保持
- Worker URL・PULL_TOKENも同じDBの `settings` テーブルに保存

## 実行・ビルド

```sh
python3 main.py        # 開発機で起動して確認(flet run でも可)
flet build linux       # Linuxデスクトップ配布物 → build/linux/
flet build apk         # Android → build/apk/
```

`flet build ios` / `flet build macos` / `flet build windows` はそれぞれの
対応OS上で実行する。この開発環境(Linux)では `flet build linux` を実際に
ビルド・起動確認済み(DB・バックアップファイル生成を確認)。Androidビルドは
未実施(実機/エミュレータがないため)。

## 実装方針(仕様書より)

- 状態管理ライブラリは使わない。SQLiteはraw SQL(標準ライブラリ `sqlite3`)で
  直接読み書きする
- 依存を増やす例外はQR/カメラ(`flet-camera` + `pyzbar` + `Pillow`)のみ
- 受信箱からの削除トリガーは「確認」操作のみ(自動削除・期限切れ削除は
  実装しない)
