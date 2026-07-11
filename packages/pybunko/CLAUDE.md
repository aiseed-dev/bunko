# CLAUDE.md ── pybunko パッケージの作業規約

## プロジェクトの目的

青空文庫のGitHubミラーの**静的ファイルだけ**に依存するPythonライブラリ。
検索・パース・HTML/EPUB/読み上げ変換を、サーバなしで読者の手元で行う。

## アーキテクチャ（3層・変更禁止）

```
catalog.py  → Library / Work（カタログ・検索・キャッシュ・取得）
parser.py   → 注記付きテキスト → Document（唯一の中間表現）
formats.py  → Document → 各出力形式（HTML / EPUB / 読み上げ文 / 今後Parquet等）
```

- 出力形式を増やすときは formats.py に関数を足す。parser.py は注記対応の拡充のみ
- Document / Paragraph / Segment の構造を壊す変更は事前に相談すること

## 絶対規則

1. **公式サーバー（aozora.gr.jp）にアクセスするコードを書かない。**
   取得はすべて `raw.githubusercontent.com/aozorabunko/aozorabunko/master/` 経由
2. **本体（install_requires）に依存を足さない。** 標準ライブラリのみ。
   重い依存は optional-dependencies（`[epub]`, `[parquet]` など）へ
3. **著作権存続作品のデフォルト除外を外さない**（`public_domain_only=True`）
4. ネットワーク取得は必ず `_fetch()`（キャッシュ経由）を通す。
   直接 `urlopen` を書かない。オフライン再現性はテストで担保する
5. テキスト処理の文字コード: 注記付きテキストはShift_JIS
   （`errors='replace'`）、カタログCSVは `utf-8-sig`

## 進捗と現在のタスク

`aozorahack/aozora2html`（Ruby, CC0-1.0）のテスト駆動移植。

**移植済み（Phase 1–6, 意味構造ファースト）**:
外字(gaiji) / 見出し(header) / 字下げ・地付き・字詰め(dir) / 傍点・傍線類(decorate) /
アクセント分解(accent) / 挿絵(img)。CC0対応表は `data/*.json` に同梱（jis2ucs, accent_table,
command_tableは decorate.py に写経）。Rubyテストは意味構造ファーストで pytest に翻訳済み。

**washi-md 連携済み（Phase 7a）**: `Document.to_markdown()`（dendenルビ `{漢字|かんじ}`）→
`to_washi_html(vertical=True)` / `to_pdf()` で aiseed-dev/washi-md に委譲（[washi]エクストラ）。

**次のタスク**:
- 上流還元: 青空の `｜`複合ルビ・**傍点(text-emphasis)** を mdit-py-cjk-friendly へPR（双方向バージョンアップ）
- 公式互換HTML `to_html(compat='aozora')` を別レンダラで（意味構造と見た目互換を混ぜない）
- Parquet一括エクスポート、縦書きリーダー統合(aozora-tegami)

- 新しい注記対応を足すときは、対応するRubyテストを意味構造ファーストで pytest に翻訳してから実装
- 外字/アクセント/装飾の対応表は aozora2html 由来を流用（自作しない）

詳細は HANDOFF.md を参照。

## テスト

```bash
pip install -e '.[epub]' pytest
pytest
```

- 回帰の基準作品: 『走れメロス』（ルビ・75段落）、『吾輩は猫である』（長編・2316段落）
- 新しい注記対応を足したら、対応するフィクスチャテストを必ず先に書く
- オフラインテスト: `urllib.request.urlopen` をモックで遮断し、
  キャッシュのみで全機能が動くことを確認する

## 文体・対外方針

- コミットメッセージ・docstringは日本語でよい
- READMEやissueでの対外的な文章は、批判を書かない。
  aozorahack「第三の柱」の文言を引用し「サーバを増やさない実装例」として提示する
- 青空文庫の注記形式そのものへの敬意を保つ（例:「ルビは読みのデータでもある」）
