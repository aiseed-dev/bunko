# aozorabunko マニュアル

青空文庫の**Shift_JIS 注記付きテキスト**を、**Unicodeに解決した構造化データ**に変換し、
そこから HTML / EPUB / 読み上げ / JSON / Parquet を生み出すためのライブラリ。

このマニュアルは「入口」と「拡張の仕方」を書いたもの。**追加作業は永久に続く**ので、
新しい注記や出力形式を足すときは、下流（parser / formats）へ積み増していけばよい。

---

## 1. 中心思想 ── Unicodeを中間に置く

```
Shift_JIS 注記付きテキスト（青空文庫の正本）
        │  parse()  ← 外字・アクセントを実Unicode文字に解決
        ▼
   Document  ＝ 一次表現（Unicodeの構造化データ）
        │
   ┌────┼───────────────┬──────────┬──────────┐
   ▼    ▼               ▼          ▼          ▼
 to_json  to_html    to_epub   to_speech   export_parquet
 (一次データ) (HTML)   (EPUB)   (読み上げ)   (コーパス)
```

- **正本は静的テキスト**。サーバもDBもAPIも要らない。放置に耐える。
- **残すべき一次表現は Document（Unicode）**。器（HTML/XHTML）は派生ビューにすぎない。
- 外字は画像でなく**実Unicode文字**。選択・検索・読み上げが効き、フォント1つで描ける。

---

## 2. インストール

```bash
pip install aozorabunko            # 本体（依存なし・標準ライブラリのみ）
pip install "aozorabunko[epub]"    # EPUB出力も使う
pip install "aozorabunko[parquet]" # Parquetコーパス出力も使う
pip install "aozorabunko[washi]"   # 縦書き・PDF組版（washi-md委譲）
```

Python 3.10+。本体はゼロ依存、重い機能だけオプション。

---

## 3. 変換：Shift_JIS → Unicode → JSON

### CLI

```bash
aozorabunko 1567_ruby_4948.zip                 # 標準出力へ JSON（1行）
aozorabunko 1567_ruby_4948.zip -o merosu.json  # ファイルへ
aozorabunko merosu.txt --indent 2              # 整形して出力
python -m aozorabunko <入力>                    # 同じ（モジュール実行）
```

入力は **`.txt` / `.zip`（中に .txt）/ URL** に対応。文字コードは Shift_JIS。

### コード

```python
from aozorabunko.convert import read_text, convert, to_json

text = read_text('1567_ruby_4948.zip')   # X-JIS → Unicode 文字列
doc  = convert('1567_ruby_4948.zip')      # → Document（parse済み）
js   = to_json('1567_ruby_4948.zip', 'merosu.json')   # → Unicode JSON
```

### カタログから一括（コーパス資産化）

```python
from aozorabunko import Library
lib = Library()                          # ミラーの作品リストCSVを取得（以後キャッシュ）
lib.export_json('aozora.jsonl', limit=100)   # 1作品1行の JSONL
lib.export_parquet('aozora.parquet')         # 段落単位の列指向（研究・NLP）
lib.index()                                  # 作家別目次（書架）データ
```

### メタデータは SQLite、本文の細部は JSON のまま

図書カード・書架情報（検索やインデックスで引くもの）は **SQLite**（標準ライブラリ
`sqlite3`・ゼロ依存）へ。作品本文の構造化データは細かいので、正規化せず
`works.doc` 列に **JSON のまま**載せる（必要時に取得して埋める）。

```python
lib.build_sqlite('aozora.db')                        # メタデータ（約1秒・全作品）
lib.build_sqlite('aozora.db', documents=True, limit=100)  # 本文JSONも埋める

from aozorabunko import db
db.search('aozora.db', '芥川')          # メタ検索（速い・部分一致）
db.authors('aozora.db')                 # 書架（作家別作品数・よみ順）
doc = db.load_document('aozora.db', '000074')   # 本文JSON → dict（無ければNone）
```

`works` テーブル: work_id(PK) / title / title_yomi / author / author_yomi / row(五十音行) /
card_url / text_url / copyrighted / **doc(本文JSON)**。再ビルドでメタは更新、doc は保持。

---

## 4. データ構造（Document / JSON スキーマ）

`Document.to_dict()` / `to_json()` が出す形。空フィールドは省略される（軽量）。
逆変換 `Document.from_dict()` で元に戻り、**JSONだけで全ビューを再生成できる**。

```jsonc
{
  "title": "走れメロス", "author": "太宰治",
  "colophon": "底本：…",                 // 底本情報（生テキスト）
  "paragraphs": [
    {
      "seg": [                            // 段落を (本文, ルビ) のセグメント列で
        { "t": "　メロスは激怒した。かの" },
        { "t": "邪智暴虐", "r": "じゃちぼうぎゃく" },   // r = ルビ＝読みデータ
        { "t": "の王を…" }
      ],
      "h": 2,                             // 見出し 2=大 3=中 4=小（本文は無し）
      "htype": "mado",                    // 見出し種別 normal/dogyo(同行)/mado(窓)
      "indent": 3,                        // 字下げ幅（em）
      "align": "right",                   // 地付き・字上げ
      "align_offset": 2,                  // 地から N 字上げ
      "jizume": 20,                       // 字詰め幅（em）
      "deco": [ {"t":"重要","cls":"sesame_dot","tag":"em"} ],  // 傍点・傍線・太字等
      "image": {"src":"…/fig1.png","w":40,"h":50,"cap":"挿絵"} // 挿絵
    }
  ]
}
```

補助プロパティ（Pythonの `Paragraph`）:
- `plain` … ルビを除いた本文、`reading` … ルビを読みとして採用したテキスト（TTS/検索向け）。

---

## 5. 拡張の仕方（永久に続く作業）

アーキテクチャは3層。**parser は注記対応の拡充、formats は出力形式の追加**に使う。
`Document / Paragraph / Segment` を壊す変更だけは事前相談。

```
catalog.py  → Library / Work（検索・取得・キャッシュ）
parser.py   → 注記付きテキスト → Document（唯一の中間表現）
formats.py  → Document → 各出力形式
```

### 5.1 新しい注記に対応する（parser.py）

移植の基準は `aozorahack/aozora2html`（Ruby, CC0）。**テスト駆動・意味構造ファースト**で進める:

1. `_ref/aozora2html/test/test_○○_tag.rb` を読み、入力注記→期待の対応を掴む。
2. それを **pytest に翻訳**（判定は自前の解決結果に対して。Rubyの厳密HTMLは仕様書として参照）。
3. `parser.py` に正規表現・解決ロジックを足す。必要なら `Paragraph` に属性追加（例: 字下げで `indent` を足した）。
4. 対応表が要るもの（外字・アクセント・装飾）は **aozora2html由来のデータを流用**し、
   `data/*.json` に同梱（`tools/build_gaiji_table.py` で再生成、実行時はjsonのみ＝ゼロ依存）。
5. 回帰は走れメロス（同梱・オフライン）と、外字を含む長編（例 吾輩は猫である）で確認。

移植順の例（要望順）: 外字 → 見出し → 字下げ/地付き → 傍点類 → アクセント → 挿絵。
（現状ここまで対応済み。訓点・font_size・keigakomi 等は同じリズムで追加可能。）

### 5.2 新しい出力形式を足す（formats.py）

`formats.py` に `to_xxx(doc)` を関数として足し、`Document` にメソッドを生やすだけ。
既存: `to_html`(compat切替可) / `to_epub` / `to_speech_text` / `to_markdown` / `to_washi_html` / `to_pdf` / `to_dict`。

### 5.3 対応表を更新する

```bash
# aozora2html を _ref/ に clone してから
python tools/build_gaiji_table.py   # data/jis2ucs.json, accent_table.json を再生成
```

---

## 6. 絶対規則（守ること）

1. **公式サーバー（aozora.gr.jp）にアクセスしない。** 取得は GitHubミラー
   （`raw.githubusercontent.com/aozorabunko/aozorabunko/master/`）経由のみ。
2. **本体（install_requires）に依存を足さない。** 標準ライブラリのみ。重い依存は
   optional-dependencies（`[epub]`/`[parquet]`/`[washi]`）へ。
3. **著作権存続作品はデフォルト除外**（`Library(public_domain_only=True)`）。
4. ネットワーク取得は必ずキャッシュ経由。オフライン再現性はテストで担保。
5. **Document が唯一の中間表現。** 出力は formats の関数として増やす。

---

## 7. テスト

```bash
pip install -e '.[epub]' pytest
pytest
```

- 完全オフライン（`conftest.py` が `urlopen` を遮断）。同梱の走れメロス（PD）で全経路を担保。
- 新しい注記対応を足したら、対応する pytest を**先に**書く（aozora2htmlのテストを翻訳）。

---

## 8. エコシステム

| リポジトリ | 役割 |
|---|---|
| **aozorabunko**（本体） | 正本→Unicode Document→各形式（読む側・このマニュアル） |
| **pyaozora** | Document→公式XHTML＋外字フォント化・埋め込み（作る側／検証） |
| **aozora-tegami** | Fletリーダー＋EPUB＋TTS（aozorabunkoの利用例） |
| aiseed-dev/**washi-md** | Markdown→縦書き・PDF組版（`[washi]`で委譲） |
| aiseed-dev/**mdit-py-cjk-friendly** | CJK対応 markdown-it-py（ルビ・傍点） |

正本さえ静的テキストで生き続ければ、検索も表示も電子書籍化も朗読も、すべて
読者の手元で・データから生やせる。このライブラリはその実演であり、入口である。
