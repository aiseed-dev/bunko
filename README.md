# 青空てのひら文庫

> 「#aozorahack では現在の青空文庫に新しい機能を付け加えたり、さまざまなデータ形式で本へのアクセスができるようなしくみを考えていきます。」
> ── #aozorahackがめざすもの「青空文庫をもっとおもしろく」より

この目標の、**サーバを増やさない実装例**です。

## これは何か

**工作員（入力・校正・保守）向けの Flet ツール群**です。変換プレビュー（カタログ検索・
ルビ付き表示）、EPUB出力（Kindle / Google Play ブックス対応）、読み上げ（VOICEVOX /
OS標準TTS）が動きます。

役割分担（全体設計は aozorabunko の DESIGN.md）:

- **読者アプリ** … Flutter（Web/iOS/Android/デスクトップ）。データ資産（SQLite＋外字フォント）を同梱して描く
- **工作員ツール** … Flet（このリポジトリ）。Pythonパイプライン（`aozorabunko`）を**直接 import** して、変換確認・外字チェック・データ資産づくりを行う

依存しているのは、次の2つ**だけ**です。

1. 青空文庫GitHubミラーの作品リストCSV（テキスト）
2. 同ミラーの注記付きテキストzip

サーバーサイドのロジックはありません。一度開いた作品は手元にキャッシュされ、以後は**オフラインでも**検索・閲覧できます。機内モードで動く図書館です。

## なぜサーバを増やさないのか

「#aozorahackがめざすもの」の第一の柱は、サーバの老朽化への対処でした。サーバは建てた瞬間から、保守・更新・費用という重さを持ち始めます。ボランティア運営のアーカイブが数十年を生き延びるには、**放置に耐える形**が要ります。

青空文庫が四半世紀生きてきた理由は、正本が静的なテキストファイルだったことにあります。テキストはミラーでき、パースでき、四半世紀前のファイルが今日そのまま読めます。このリポジトリは、その正本さえ維持されていれば、検索も、表示も、電子書籍化も、朗読も、すべて**読者の手元で**生やせることの実演です。新しい機能は、サーバに足すのではなく、テキストから生やす。

## 使い方

```bash
pip install "aozorabunko[epub]" flet
flet run aozora_shinkan.py          # 変換プレビュー（検索→閲覧・外字も実文字表示）
python aozora2epub.py <zipのURL>    # EPUB変換（Send to Kindle等へ）
```

検索・取得・パース・変換は [`aozorabunko`](https://github.com/aiseed-dev/aozorabunko) ライブラリに委譲しています。このリポジトリは**ライブラリの利用例であり、工作員の作業台**です。

読者アプリ（Flutter）に同梱するデータ資産づくり:

```bash
python -c "from aozorabunko import Library; Library().build_sqlite('aozora.db')"
python -m pyaozora.fonts aozora-gaiji.woff2   # 真の外字4,330字（≈2.8MB）
```

読み上げ（任意）:

```bash
# 高品質: VOICEVOX (https://voicevox.hiroshiba.jp/) を起動しておく
# 手軽:   pip install pyttsx3
python aozora_tts.py                # 変換デモ
```

## 構成

| ファイル | 役割 |
|---|---|
| `aozora_shinkan.py` | 変換プレビュー（UIのみ。検索・パースは `aozorabunko` に委譲） |
| `aozora2epub.py` | 注記付きテキスト → EPUB3 変換（`aozorabunko.parse` + `to_epub`） |
| `aozora_tts.py` | 読み上げテキスト生成・TTSエンジン接続（ルビ＝読みデータ） |

技術メモ:

- **ルビは読みのデータでもある**: `邪智暴虐《じゃちぼうぎゃく》` のルビを読み上げ時の読みとして使うため、TTSが難読漢字を誤読しません。青空文庫の注記形式ならではの利点です。
- **カタログはCSV一枚**: `index_pages/list_person_all_extended_utf8.zip` に全作品・全著者・よみ・著作権フラグが揃っています。著作権存続作品はデフォルトで除外しています。
- **公式サーバーには触りません**: 取得はすべてGitHubミラー（raw.githubusercontent.com）経由です。

## ロードマップ（工作員ツールとして）

- [x] 注記対応の拡充（外字のUnicode解決・字下げ・傍点 → `aozorabunko` 側で対応済み）
- [ ] 未対応注記・未解決外字（〓）の検出パネル
- [ ] データ資産づくりのGUI（build_sqlite / フォント生成 / 図書カード取り込み）
- [ ] pyaozora ゴールデン検証の diff 表示
- [ ] 読み上げの統合（段落ハイライト同期）

縦書き表示・読者向けUIは Flutter 読者アプリ側で（aozorabunko/DESIGN.md 参照）。

## ライセンス

コードはMITライセンスです。青空文庫の収録ファイルの利用は「[青空文庫収録ファイルの取り扱い規準](https://www.aozora.gr.jp/guide/kijyunn.html)」に従ってください。

---

*来年、青空文庫は30周年を迎えます。テキストの正本という贈り物が、これからの30年も放置に耐えて生き続けますように。*
