# HANDOFF.md ── 青空文庫Python化プロジェクト 引き継ぎ文書

作成: 2026-07-11（Claude.ai セッションからの引き継ぎ）
引き継ぎ先: Claude Code

## 0. プロジェクトの一言要約

青空文庫の静的なテキスト正本**だけ**に依存するPythonライブラリ `aozorabunko` を育て、
aozorahack「第三の柱」（さまざまなデータ形式で本へのアクセス）の
**サーバを増やさない実装**として公開する。

## 1. 完成済みの成果物（このセッションで検証済み）

| 成果物 | 状態 | 内容 |
|---|---|---|
| `aozorabunko-py/` | 動作検証済み | pipパッケージ。Library/Work/Document の3層。`pip install -e .` で導入し、検索→パース→HTML/EPUB/読み上げの全パスをテスト済み |
| `aozora-tegami/` | 動作検証済み | Fletリーダーアプリ「青空てのひら文庫」＋EPUB変換＋TTSモジュール。オフライン動作をurlopen遮断で検証済み |
| `ai_search_gateway.py` | 動作検証済み | 会員制AI検索の関所（JWT検証・クォータ・SSE）。将来のRAG司書用 |

### aozorabunko パッケージの構成

```
aozorabunko/
  catalog.py   # Library（カタログ・検索・キャッシュ）, Work（作品・取得）
  parser.py    # 注記付きテキスト → Document（共通中間表現）
  formats.py   # Document → HTML / EPUB / 読み上げ文リスト
```

- 中間表現 `Document`（title, author, paragraphs[Segment], colophon）が要。
  出力形式の追加は formats.py に関数を足すだけ。パーサーは触らない。
- `Paragraph.reading` はルビを読みとして採用したテキスト。TTSの誤読対策の要。

### 検証済みの事実（再確認不要）

- カタログ: パブリックドメイン 17,744作品 / 全18,089エントリ（著者行・テキストURLあり）
- PyPI名 `aozorabunko` / `aozora` / `aozora-bunko` は空き（2026-07-11時点）
- GitHubミラーのraw URL変換: `www.aozora.gr.jp/(cards/...)` → `raw.githubusercontent.com/aozorabunko/aozorabunko/master/cards/...`
- カタログCSV: `index_pages/list_person_all_extended_utf8.zip`（UTF-8 BOM付き、役割フラグ・著作権フラグあり）
- 注記付きテキストはShift_JIS。zipは `PK` マジックで判定
- ebooklib生成のEPUB3は、Google Play ブックスでEPUB2互換のカバー指定がないと処理失敗の報告あり（対応は後述ロードマップ）

## 2. 最優先タスク: aozora2html のテスト駆動移植

### 背景

- `aozorahack/aozora2html`（Ruby, **CC0-1.0**, 2026年1月も更新）は注記→HTML変換のリファレンス実装
- テストスイートが注記仕様の全域を機械可読に記述している（test/ 配下、minitest）
- 確認済みのテストファイル群: gaiji（外字）, accent, decorate, font_size, img,
  keigakomi, yokogumi, dakuten_katakana, header, dir, editor_note, inline_caption ほか
- CC0なので移植に法的障害なし。移植後はRuby版と同じテストを共有する「兄弟実装」になる

### 手順（テスト駆動移植）

1. `git clone https://github.com/aozorahack/aozora2html` して test/ と lib/ を読む
2. 注記1種類ごとに: Rubyテストのフィクスチャ（入力→期待HTML）を pytest に翻訳 →
   lib/ の該当実装を parser.py / formats.py に移植 → フィクスチャで検証
3. 移植順（要望の多い順）:
   1. **外字（gaiji）** ← 最優先。`※［＃「木＋若」、第3水準1-85-1］` 形式の
      JIS X 0213 面区点 → Unicode 解決。対応表は aozora2html リポジトリ内の
      データを流用する（自前で表を作らない）
   2. 見出し（header）── 現行実装は簡易版なので置き換え
   3. 字下げ・地付き（dir 系）── Documentにレイアウト属性を追加する設計変更を伴う
   4. 傍点・傍線・圏点類（decorate）── 現行は傍点のみ。網羅する
   5. アクセント分解（accent）── 〔 〕記法
   6. 挿絵（img）── ミラーURLへの画像参照として
4. 注意: aozora2htmlの期待HTMLは公式サイトのXHTML形式（クラス名等が公式流儀）。
   **Documentの構造化を正とし、公式互換HTMLは formats.py に `to_html(compat='aozora')`
   として別レンダラで足す**方針を推奨。意味構造と見た目互換を混ぜない。

### 完了条件

- aozora2htmlのテストフィクスチャ由来のpytestが全部通る
- 『吾輩は猫である』級の長編でパースが落ちない（既存の検証を回帰テスト化する）

## 3. ロードマップ（優先順）

1. aozora2html移植（上記）
2. **Parquet一括エクスポート**: 全作品コーパスを列指向で書き出す
   （研究・NLP・RAG用途。pyarrowはオプショナル依存 `[parquet]` に）
3. **EPUBのPlay ブックス互換**: EPUB2互換カバー指定（`<meta name="cover">`)＋表紙画像。
   `to_epub(path, target='playbooks')` のようなプロファイル切替
4. 縦書き対応（EPUB CSSの writing-mode、コメントアウト済みの雛形が _CSS にある）
5. TTSのリーダー統合（aozora-tegami側。段落ハイライト同期、設計コメントは aozora_tts.py 末尾）
6. ローカルLLM司書（RAG）。ai_search_gateway.py が関所の雛形

## 4. 守るべき設計原則（変更しないこと）

1. **依存はGitHubミラーの静的ファイルのみ**。公式サーバー（aozora.gr.jp）には一切アクセスしない
2. **本体はゼロ依存**（標準ライブラリのみ）。重い依存はオプショナルエクストラへ
   （現状: `[epub]` → ebooklib。今後: `[parquet]` → pyarrow）
3. **著作権存続作品はデフォルト除外**（`public_domain_only=True` が既定）
4. **取得は必ずキャッシュ経由**（二度目からオフラインで動くこと。テストで担保する）
5. **Documentが唯一の中間表現**。出力形式はformats.pyの関数として増やす
6. 対外的な言葉遣い: 批判をしない。aozorahack「第三の柱」の文言を引用し、
   「サーバを増やさない実装例」として提示する（詳細は aozora-tegami/README.md の書き方を踏襲）

## 5. エコシステム戦略

- **aozora2html**（Ruby, 現役, CC0）: テスト駆動で移植。兄弟実装として敬意を保つ
- **aozora-cli**（Python, 現役, MIT）: 競合しない。こちらがライブラリ層、
  aozora-cliがCLI層という補完を提案（先方issueで対話してから）
- **pubserver2**(JS, 2023年停止): 移植しない。APIサーバーの機能は
  Library＋Parquetエクスポートで置き換わる（サーバの再建はしない）
- **aozora-parser.js**（2019年WIP停止）: パーサー移植が人手不足で止まった前例。
  今回はAI移植でコストが下がったことの実証になる

## 6. 公開手順（コードが揃ってから）

1. GitHubに `aozorabunko-py` リポジトリ作成、CLAUDE.md込みでpush
2. pytest＋GitHub ActionsでCI（Python 3.10/3.11/3.12）
3. PyPIへ `aozorabunko` として公開（名前確保済みであることは確認済、早めに）
4. aozorahack org のdiscussion/issueに一行＋リンクで提示
   （READMEに語らせる。長い説明を書かない）
5. 別途、青空てのひら文庫（aozora-tegami）をライブラリの最初の利用者として
   `import aozorabunko` に書き直す

## 7. 背景文脈（判断に迷ったときのための思想）

このプロジェクトの原則は一貫して:
**正本はテキスト。機能はサーバに足さず、テキストから読者の手元に生やす。**

青空文庫が四半世紀生き延びたのは正本が静的テキストだったから。
ボランティア運営のアーカイブが「20年の冬」（次のPD解禁は2038年）を越えるには、
放置に耐える形が必要。サーバは保守され続ける限りしか生きないが、
静的ファイルは放置されても死なない。このライブラリはその思想の実演である。
