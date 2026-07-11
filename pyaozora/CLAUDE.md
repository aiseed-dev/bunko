# CLAUDE.md ── pyaozora 作業規約

## 目的

青空文庫の注記付きテキスト → **公式サイトと同じXHTML**を、Pythonで生成する。
入力（`NNNN_ruby_XXXX.zip`）と正解出力（`NNNN_XXXXX.html`）が本家リポジトリに
両方あるので、**ゴールデンファイルでバイト比較して正しさを検証する**のが核心。

## アーキテクチャ

```
converter.py  → to_official_html / to_official_bytes（公式XHTMLの組み立て）
```

- 注記の解釈は `aozorabunko`（姉妹ライブラリ）に委譲する。pyaozora はパーサを持たない。
- pyaozora は「公式流儀のページ組み立て」に徹する:
  ルビは `<ruby><rb>…</rb><rp>（</rp><rt>…</rt><rp>）</rp></ruby>`、
  改行は `<br />`（空行も保持）、head/metadata/main_text/底本/表記について/図書カード。

## 絶対規則

1. **ゴールデン比較で検証する。** 変更のたびに `pytest`（走れメロスのバイト一致）を通す。
   一致率を上げる作業は、公式ファイルとの diff を見て差分を潰す。
2. **aozorabunko のパース結果を使う。** 注記解釈を pyaozora で再実装しない
   （空行保持が要る場合は `parse(text, keep_blank_lines=True)`）。
3. 出力の符号化は **Shift_JIS・CRLF**（公式ファイルと同じ）。`to_official_bytes` で確認。

## 既知の課題（次の反復）

- **外字の画像モード**: 公式HTMLは第3・第4水準外字を `<img class="gaiji">` で埋め込む。
  aozorabunko はUnicodeに解決するため差が出る。公式の画像モードを pyaozora で再現する。
- 底本ブロックのボイラープレート差、見出しの細部、【】記号説明ブロックの扱い。

## テスト

```bash
pip install -e .
pytest    # 走れメロスのバイト完全一致 ＋ 骨格・ルビ形式
```

- ゴールデンは `tests/golden/`（走れメロス＝PD作品の入出力ペアを同梱）。
- 新しい作品で一致率を測るときは、その作品のカードから zip と html を取得して diff する。
