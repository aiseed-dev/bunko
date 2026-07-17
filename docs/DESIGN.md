# 設計書 ── 青空文庫 Python スタック

作成: 2026-07-11。この文書が全体設計の正本（置き場: **bunko/docs/**）。使い方の詳細は [MANUAL.md](MANUAL.md)。

> **改定（2026-07-18）: エディタ（AISeed工房→pykobo）と FormRescue（→forms）を独立リポジトリに分離。**
> bunko は青空文庫そのもの（pybunko＋データ資産＋docs）に純化し、運用を担う。
> エコシステム: pykobo=エディタ（pywashi/pyasciidoc/pybunkoを関連コンポーネント
> として使う）／forms=webフォームの道具（cf-publishが関連コンポーネント）／
> 文庫の問い合わせは aiseed-migration-kit のテナント（サンプル）として実装する。
>
> **改定（2026-07-17）: Flutter 読者アプリ（app/bunko）を廃止。**
> Webでの読書は青空文庫本体があるため、読者向けの独自アプリは持たない。
> 書架・目次のような一覧は静的サイトで足りる（tools/examples/ に試作）。
> Dartパーサとの「スキーマ往復互換」要件も消滅し、パーサは parser.py の
> 1本になった。本文書中の Flutter への言及は決定当時の記録として残す。
> コードは git 履歴（〜2026-07-17）から復元できる。

## 0.5 bunko リポジトリの構成（モノレポ）

```
bunko/
├── pybunko/          # Pythonライブラリ（中核＋official＋fonts＋xlsx）
├── tests/            # 153テスト（完全オフライン）※PyPI未登録・editable/git指定で利用
├── assets/           # データ資産（aozora.db・IPAex明朝・jis2ucs.json・cp932.bin）
├── tools/            # build_assets.py・build_gaiji_table.py・examples/
└── docs/             # この設計書・マニュアル・LICENSING（正本）
```

## 0. 一言要約

**正本（静的テキスト）→ Unicode構造化データ（一次表現）→ 工作員はFlet、一覧は静的サイト。**
変換・検証・データ資産づくりはPythonが担う。サーバは建てない。

## 1. 思想（変わらないもの）

1. **正本はテキスト。** 機能はサーバに足さず、テキストから読者の手元に生やす。
   青空文庫が四半世紀生きたのは正本が静的テキストだったから。放置に耐える形を保つ。
2. **Unicodeを中間に置く。** 外字・アクセントは実Unicode文字に解決する。
   器（HTML/XHTML）は派生ビューにすぎず、残すべき一次表現は構造化Unicodeデータ。
3. **公式サーバー（aozora.gr.jp）には触れない。** 取得はGitHubミラーの静的ファイルのみ、
   必ずキャッシュ経由（二度目からオフライン）。著作権存続作品はデフォルト除外。
4. **コアはゼロ依存。** 標準ライブラリのみ。重い機能はオプショナルエクストラへ。

## 2. 全体アーキテクチャ

```
┌─ 正本層 ──────────────────────────────────────────────┐
│ aozorabunko/aozorabunko GitHubミラー（静的ファイルのみ）      │
│  ・注記付きテキスト zip（Shift_JIS）   ・図書カード cardNNNN.html │
│  ・作家別作品一覧CSV（カタログ）                             │
└──────────────┬─────────────────────────────────┘
               │ 取得は必ずキャッシュ経由
┌─ 変換層（Python: pybunko）───────────────────────────┐
│ parse: 注記 → Document（外字・アクセントをUnicodeに解決）      │
│ catalog/card: カタログ・図書カード → 構造化メタ               │
└──────────────┬─────────────────────────────────┘
               ▼
┌─ データ層（一次データ資産・これが「残すもの」）───────────────┐
│ ・Document JSON（作品ごと。seg/ルビ/見出し/字下げ/装飾/挿絵）    │
│ ・SQLite aozora.db（書架メタ＋doc/card JSON列。1ファイル）      │
│ ・外字サブセットフォント（真の外字4,330字 ≈2.8MB WOFF2）        │
└──────┬───────────────┬───────────────┬─────────┘
        ▼                 ▼                 ▼
┌─ アプリ層 ──────┐ ┌─ 工作員層 ─────┐ ┌─ 派生ビュー ────┐
│ 読者アプリ =       │ │ 工作員ツール =    │ │ HTML / EPUB / PDF │
│ **Flutter**       │ │ **Flet(Python)** │ │ Parquet / 朗読    │
│ Web/iOS/Android/  │ │ 変換確認・校正・   │ │ （formats.py）     │
│ デスクトップ        │ │ DB構築・検証      │ │                  │
└─────────────┘ └─────────────┘ └─────────────┘
```

## 3. 決定記録（ADR）

| # | 決定 | 理由 |
|---|---|---|
| 1 | **Unicode中間表現** | 外字を画像でなく実文字に。選択・検索・読み上げが効き、フォント1つで描ける。器は後からいくらでも生成できる |
| 2 | **SQLite＋JSON** | 書架・図書カードのメタは SQLite（検索・集計・結合が速い、標準lib）。本文・カードの細部は正規化せず doc/card 列に JSON のまま |
| 3 | **読者アプリは Flutter** | 1コードで Web/iOS/Android/デスクトップ。テキスト描画性能・フォント同梱・配布性。**Flutter Webで足りるので静的XHTMLは不要**（器はデータから随時生成） |
| 4 | **工作員ツールは Flet** | 変換・校正・検証は Python パイプライン（pybunko）と**同一言語・同一プロセス**で直接呼べるのが速い。工作員は少数でPython環境を持てる。読者向けの配布品質は不要 |
| 5 | **外字はフォントで**（画像廃止） | 真の外字（JIS X 0208外）は4,330字→WOFF2約2.8MB。アプリに1フォント同梱すれば全外字を実文字表示。作品単位なら数KB（使用字のみサブセット） |
| 6 | **公式XHTML再現は凍結維持** | pybunko.official の image既定はバイト完全一致（走れメロス・桜の樹）。兄弟実装・検証器として価値はあるが、以後は投資しない（ADR-3の帰結） |
| 7 | **ゼロ依存コア** | pybunko 本体は標準ライブラリのみ。epub/washi/parquet/font はエクストラ。ビルド時のみの依存（pyyaml/fonttools）は実行時に持ち込まない |
| 8 | **傍点等の上流還元** | CJK組版の汎用機能は aiseed-dev スタック（mdit-py-cjk-friendly / washi-md）へ還元し、青空側は利用者になる（bouten プラグイン `[対象]{.class}`） |

## 4. リポジトリ構成と責務

| リポジトリ | 層 | 責務 | 状態 |
|---|---|---|---|
| bunko/**app/pykobo/pybunko** | 変換・データ | 正本→Document(Unicode)→JSON/SQLite/EPUB/…。カタログ・図書カード・official・fonts。**中核**（PyPI個別登録はしない） | 98テスト |
| **bunko** | 読者＋資産＋docs | **モノレポ**: app/bunko=Flutter読者アプリ（dev.aiseed.bunko）／app/pykobo/pybunko=Python側一体（中核＋official＋fonts・PyPI個別登録なし）／assets/=共有データ資産／app/pykobo=Flet工作員ツール「AISeed工房」／tools/=開発スクリプト／docs/=正本 | 13＋98テスト |
| aiseed-dev/washi-md | 組版 | Markdown→縦書き/原稿用紙/PDF（[washi]で委譲） | 23テスト |
| aiseed-dev/mdit-py-cjk-friendly | 組版基盤 | CJK対応 markdown-it-py（ルビ・傍点bouten） | 52テスト |
| aiseed-dev/flutter_svg_cjk_friendly | Flutter補助 | SVGのCJK font/縦書き修正（Flutterアプリで必要時） | — |
| aozorahack/aozora2html | 参照 | Ruby参照実装（CC0）。テスト・対応表の出典。非管理clone（_ref/） | — |

## 5. データ設計

### 5.1 Document JSON（一次表現・詳細は MANUAL §4）

```jsonc
{ "title": "…", "author": "…", "colophon": "…",
  "paragraphs": [ { "seg": [ {"t":"本文"}, {"t":"漢字","r":"よみ"} ],
                    "h":2, "indent":3, "deco":[…], "image":{…} } ] }
```
- 外字・アクセントは**解決済みの実Unicode文字**。ルビ `r` は読みデータ（TTS・検索に使える）。
- `Document.from_dict()` で往復可能 ＝ このJSONだけで全ビューを再生成できる。

### 5.2 SQLite（aozora.db・1ファイル）

```sql
works(work_id PK, title, title_yomi, author, author_yomi,
      row,             -- 五十音行（書架タブ用）
      card_url, text_url, copyrighted,
      doc  TEXT,       -- 本文JSON（未取得はNULL。取得次第埋める）
      card TEXT)       -- 図書カードJSON（底本・入力者・生没年・ファイル一覧）
```
- メタは UPSERT で更新、doc/card は保持。ALTER による前方マイグレーション。
- 実測: 全カタログ 17,335作品/981作家 → 約1秒・5.6MB（メタのみ）。
- 既知の割り切り: work_id 主キーのため共著は1行（副著者は card JSON 側に全員残る）。

### 5.3 フォント資産

| 資産 | 用途 | サイズ |
|---|---|---|
| `python -m pybunko.fonts out.woff2` | アプリ同梱用・真の外字4,330字 | ≈2.8MB |
| 作品単位サブセット（embed_font=True） | 自己完結HTML・使用字のみ | 数KB |
| IPAex明朝 等まるごと | 本文＋外字を1フォントで | ≈7.5MB |

## 6. アプリ設計

### 6.1 Flutter 読者アプリ（app/bunko ── 完成・v0.1.0）

- **同梱**: `aozora.db`（メタ5.6MB。人気作品の doc を事前充填してもよい）、
  外字フォント `aozora-gaiji.woff2`（2.8MB）または IPAex明朝まるごと。
- **画面**: 書架（五十音行タブ・検索 = `row`/`*_yomi` 列で即）→ 図書カード（`card` JSON:
  底本・入力者・生没年）→ 読書（`doc` JSON: 縦書き・ルビ・外字実文字）。
- **データアクセス**: sqflite/drift で works を引き、doc/card 列の JSON をデコードして描画。
  未取得の作品はミラーから注記テキストを取得 →（当面）Python変換済み配布物 or
  将来的に Dart 側パーサ移植で doc を充填。
- **描画**: ルビは `WidgetSpan`/自前レイアウト。縦書きは自前 or パッケージ
  （flutter_svg_cjk_friendly の縦書き知見を流用）。**外字は普通のテキスト描画**（それがこの設計の成果）。
- プロトタイプの意匠・挙動は examples の2つのビューア（書架・縦書き読書）が仕様を兼ねる。

### 6.15 重作業ノード（ローカルAIマシン ── 例: MS-S1 MAX）

大容量統合メモリのAIミニPC（Ryzen AI Max+ 395 / 128GB級）を、工房の**重作業ノード**として使う。
読者アプリの「サーバ不要」原則はそのまま ── これは**生成時だけ**動く自分の機械。

1. **朗読パック量産**: 日本語の本命は **Style-Bert-VITS2**（AGPL・内蔵FastAPIサーバ→
   `--engine sbv2 --base-url http://<node>:5000`）。OpenAI互換サーバ（Kokoro-FastAPI等→
   `--engine openai`）にも対応。クラウド（edge-tts）依存が消え、代表作のバッチ生成が一晩で回る
2. **ローカルLLM司書（RAG）**: Ollama/llama.cpp の OpenAI互換APIに、コーパス
   （SQLite/JSONL/Parquet）検索を組み合わせて「紹介・推薦・質問応答」を手元で
   （HANDOFF当初のロードマップ項目）
3. **埋め込み索引の事前計算**: 全作品の意味検索インデックスを資産として生成し、
   書架の「意味で探す」へ
4. **底本ページの書き起こし（VLM入力）**: スマフォのカメラで底本を撮り、工房
   （Web・LAN内）へ送る → ノード上のOSSのVLM（Qwen-VL等、OpenAI互換APIで
   `pybunko.vision`）が青空文庫注記形式の下書きに書き起こす → 機械チェック
   （`pybunko.kosei`）→ Claude校正。従来の「スキャナ＋OCR＋手修正」の置き換え

### 6.2 Flet 工作員アプリ（app/pykobo ── AISeed工房）

- **役割**: 読者向けではなく**工作員（入力・校正・保守）向け**。Pythonパイプラインを直接呼ぶ。
  - 新規作品の変換確認: 注記テキスト → Document → プレビュー（未対応注記の検出）
  - 外字解決チェック: 未解決（〓）一覧・面区点の確認
  - データ資産の構築: `build_sqlite`（メタ/doc/card）・フォント生成
  - official（公式XHTML）ゴールデン検証: 正解HTMLとの diff 表示
- 既存の `aozora_shinkan.py`（Fletリーダー）は工作員のプレビューベンチとして温存。
  `aozora2epub.py` / `aozora_tts.py` も工作員ツール群の一部。

## 7. ロードマップ

1. ~~Flutter 読者アプリの起工~~ → **完成（bunko v0.1.0）**。次: Android/iOSビルド・
   Web版のIndexedDB永続化・縦書きの禁則/挿絵対応・アプリ内の底本更新
2. ~~Flet 工作員ツールの再構成~~ → **完成（AISeed工房 aozora_kobo.py）**: 検査/資産/検証の3タブ
2.5 朗読パック: 生成側は**完成**（pybunko.audio ── VOICEVOX/edge-tts→Opus＋段落manifest）。
    アプリ側の再生（just_audio等＋manifestシーク・ハイライト同期、端末TTSへのフォールバック）が次
3. 共著の正規化（work_authors テーブル）が必要になったら追加
4. 注記の追加対応（訓点・送り仮名・字の大きさ・罫囲み等）── MANUAL §5.1 のリズムで
5. 公開: ~~GitHub push~~（済: aiseed-dev/bunko）。PyPIへの個別登録はしない（ユーザー決定）。
   次は aozorahack への提示（「サーバを増やさない実装例」として）

## 8. 検証の考え方

- **オフライン再現性**: 全テストは urlopen 遮断で回る（正本キャッシュ同梱）。
- **ゴールデン**: pybunko.official は公式XHTMLとバイト比較（入力と正解が両方ミラーにある）。
- **回帰の基準作品**: 走れメロス（ルビ）・吾輩は猫である（長編・外字35）・山月記（外字22）・
  変身（翻訳者）・風の又三郎（挿絵）。
- 現在: pybunko 98 / Flutter 13（＋外部リポ: mdit-py 52 / washi-md 23）＝ **111＋75テスト グリーン**。
