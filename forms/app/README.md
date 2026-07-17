# FormRescue

WordPressの問い合わせフォームから分離した受信箱(Cloudflare Worker + D1、または
自社サーバー)を、ローカル端末に取りに行く(プル型)ための管理アプリ。

仕様の全文は [`website/docs/plan/wordpress/todo.md`](../../../website/docs/plan/wordpress/todo.md)
の「管理アプリの仕様」を参照。このアプリはそこで定義された仕様の実装(Flutter版)。

## 初回設定

`deploy.py`(または `cf-publish`)を実行すると、Worker URLと PULL_TOKEN を含む
QRコードが端末画面に表示される。アプリ初回起動時の設定画面でこれを読み取るか、
手入力する。

QRコードの中身は次のJSON形式であること(このアプリが読み取れる契約):

```json
{"url": "https://xxxx.workers.dev", "token": "xxxxxxxx..."}
```

- `url` は `https://` で始まる必要がある
- QRカメラ読み取りは Android / iOS / macOS のみ対応(`mobile_scanner` の制約でLinux/Windowsは非対応)。その場合は手入力欄を使う

## データの保存場所

- SQLite: OS標準のアプリデータ領域(`path_provider` の `getApplicationSupportDirectory`)配下の `data/inbox.db`
- バックアップ: 同領域の `backups/inbox-YYYYMMDD.db`。起動時に1日1回作成し、直近30日分を保持
- Worker URL・PULL_TOKENも同じDBの `settings` テーブルに保存(端末の外には出ない)

## 実行・ビルド

```sh
flutter pub get
flutter run -d linux      # デスクトップ(開発機で確認)
flutter build linux       # Linuxデスクトップ配布物
flutter build apk         # Android
```

iOS/macOS/Windows向けビルドはそれぞれの対応OS上で `flutter build ios` /
`flutter build macos` / `flutter build windows` を実行する(このリポジトリの
開発環境がLinuxのため、雛形とコードはあるが実機ビルド確認はLinuxとAndroidのみ)。

## 実装方針(仕様書より)

- 状態管理ライブラリは使わない。SQLiteはraw SQLで直接読み書きする
- 依存を増やす例外はQR/カメラ(`mobile_scanner`)のみ。認証情報の手入力ミスを防ぐため
- 受信箱からの削除トリガーは「確認」操作のみ(自動削除・期限切れ削除は実装しない)
