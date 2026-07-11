# aozorabunko

青空文庫をPythonから。

```python
from aozorabunko import Library

lib = Library()
work = lib.search('走れメロス')[0]
doc = work.document()

doc.to_epub('merosu.epub')      # Send to Kindle / Play ブックスへ
html = doc.to_html()            # <ruby> タグ付きHTML
sentences = doc.to_speech_text()  # TTS向け（ルビを読みとして採用）
```

## 設計原則

このライブラリが依存するのは、[aozorabunko/aozorabunko](https://github.com/aozorabunko/aozorabunko) GitHubミラーの**静的ファイルだけ**です。

- サーバーサイドのロジックなし。データベースなし。APIなし
- 公式サーバー（aozora.gr.jp）には一切アクセスしない
- 取得結果は `~/.cache/aozorabunko` にキャッシュされ、二度目からオフラインで動く
- 著作権存続作品はデフォルトで除外（`Library(public_domain_only=False)` で含められる）

正本が静的テキストである限り、検索も、パースも、電子書籍化も、読み上げも、すべて手元で実現できます。このライブラリはその実演です。

> 「#aozorahack では現在の青空文庫に新しい機能を付け加えたり、さまざまなデータ形式で本へのアクセスができるようなしくみを考えていきます。」
> ── #aozorahackがめざすもの より

## インストール

```bash
pip install aozorabunko          # 本体（依存なし・標準ライブラリのみ）
pip install aozorabunko[epub]    # EPUB出力も使う場合
```

## API

### Library

```python
lib = Library()                      # カタログ取得（初回のみ、以後キャッシュ）
lib.search('なつめそうせき')          # 作品名・著者名・よみの部分一致
lib.by_author('宮沢賢治')            # 著者の全作品
lib.works                            # 全17,000+作品のリスト
```

### Work

```python
work.title, work.author              # 書誌
work.text()                          # 注記付きテキスト（正本そのもの）
work.document()                      # パース済みDocument
```

### Document

```python
doc.paragraphs                       # 段落のリスト（ルビ・見出し・傍点を構造化）
doc.paragraphs[0].plain              # プレーンテキスト
doc.paragraphs[0].reading            # ルビを読みとして採用（誤読しないTTS入力）
doc.colophon                         # 底本情報
doc.to_html() / to_epub(path) / to_speech_text()
```

## 何に使えるか

- **リーダーアプリ**の土台（Flet / Flutter バックエンド / CLI）
- **電子書籍化パイプライン**（一括EPUB変換 → Kindle・Play ブックス）
- **朗読・オーディオブック**（`reading` はルビ由来なので難読漢字を誤読しない）
- **研究・NLP・RAG**（構造化済みの近代日本語コーパスとして）

## ロードマップ

- [ ] 外字注記のUnicode解決（`※［＃「木＋若」…］` → 文字）
- [ ] 字下げ・地付きなどレイアウト注記の構造化
- [ ] Parquet一括エクスポート（全作品コーパスをデータ分析へ）

## ライセンス

コードはMIT。収録ファイルの利用は「[青空文庫収録ファイルの取り扱い規準](https://www.aozora.gr.jp/guide/kijyunn.html)」に従ってください。
