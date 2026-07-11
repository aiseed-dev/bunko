# 文庫（bunko） — Flutter 読者アプリ

青空文庫を第一の蔵書とするオフライン読書アプリ本体。
リポジトリ全体の説明は [ルートのREADME](../../README.md)、設計は [docs/DESIGN.md](../../docs/DESIGN.md)。

```bash
flutter test
flutter build web --release      # Web（web/sqlite3.wasm 同梱済み）
flutter build linux --release    # Linux デスクトップ
flutter build apk --release      # Android（applicationId: dev.aiseed.bunko）
# iOS / macOS は Mac 上で、Windows は Windows 上でビルド
```

共有データ資産（../../assets への symlink）は `python ../../tools/build_assets.py` で再生成。
