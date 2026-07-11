# pyaozora

青空文庫の**注記付きテキスト**を、公式サイトと同じ**XHTML**に変換する。

```python
from pyaozora import to_official_html, to_official_bytes

text = open('1567_ruby_4948.txt', encoding='shift_jis').read()
html = to_official_html(text)          # 公式流儀のXHTML1.1（文字列）
data = to_official_bytes(text)         # Shift_JIS バイト列（公式ファイルと同じ符号化）
```

## 何をするものか

青空文庫のGitHubミラー [aozorabunko/aozorabunko](https://github.com/aozorabunko/aozorabunko) には、
**入力（注記付きテキスト `NNNN_ruby_XXXX.zip`）** と **正解出力（公式XHTML `NNNN_XXXXX.html`）** の
両方が入っています。pyaozora は「基本データとPythonだけ」でその公式HTMLを再生成し、
**既存の公式ファイルとバイト単位で突き合わせて検証**します。入力と正解が揃っているので、
差分を潰して正しさを機械的に確かめられる ── そういうタスクです。

注記の解釈（外字・ルビ・見出し・字下げ・傍点・アクセント・挿絵）は姉妹ライブラリ
[`aozorabunko`](https://github.com/aiseed-dev/aozorabunko) に委譲し、pyaozora は
公式流儀のページ組み立て（`<rb>`/`<rp>`ルビ、`<br />`改行、head/底本/図書カード）に徹します。

- **aozorabunko** = アーカイブを**読む**側（作品→HTML/EPUB/TTS/Parquet）
- **pyaozora** = アーカイブを**作る**側（注記テキスト→公式XHTML）

## 検証（ゴールデンファイル）

```bash
pip install -e .
pytest
```

同梱の走れメロス（太宰治・パブリックドメイン）で、生成結果が公式ファイル
`1567_14913.html` と **27,570バイト完全一致**することをテストします。

## 到達状況

| 作品 | 一致 |
|---|---|
| 走れメロス | ✅ バイト完全一致 |
| 桜の樹の下には | ✅ バイト完全一致 |
| 山月記（第3・第4水準外字あり） | 〜95% |
| こころ・人間失格 | 〜90-92% |

外字の画像モードと、底本ブロックのルビ描画は対応済み。残りは各作品の細部
（見出しの一部・特殊注記）で、公式ファイルとの diff を潰して詰めていきます。

## 外字モード（画像 or フォント）

```python
to_official_html(text)                              # 既定 = image：公式と同じ <img class="gaiji">
to_official_html(text, gaiji='font')                # font：実Unicode文字 <span class="gaiji">
to_official_html(text, gaiji='font', embed_font=True)  # font＋サブセット埋め込み（自己完結）
```

青空文庫が2000年に外字を**画像**にしたのは、当時のフォントが第3・第4水準漢字を
表示できなかったからです。今は Unicode にほぼ存在し、`aozorabunko` が実文字に解決します。

- `gaiji='image'`（既定）… 公式ファイルとのバイト完全一致を保つ。
- `gaiji='font'`（現代版）… 外字を**実Unicode文字**で出し、head に JIS X 0213 対応
  フォント（IPAmj明朝・Noto Serif CJK JP 等）を指定。**選択・検索・読み上げが効き、
  11,000枚のPNG依存も消える**。例: 山月記は画像22枚 → 実文字22文字（`虢`『傪』…）。

Unicode化できない外字（非0213の合成説明）だけは注記スパンにフォールバックします。

### サブセット埋め込み（`embed_font=True`, 自己完結）

`embed_font=True` で、その作品で使う外字のグリフ**だけ**を元フォント（IPAex明朝等）から
切り出して WOFF2 にし、`@font-face` の `data:` URI として head に埋め込みます。閲覧側に
JIS X 0213対応フォントが無くても確実に表示され、しかも埋め込みは数十字ぶんで済みます。

例: 山月記は外字が延べ22箇所でも**ユニークは4字**（傪嘷虢軺）→ 埋め込み WOFF2 は約**4.9KB**、
ページ全体で約35KB。`.gaiji` スパンにだけ適用するので本文は通常フォントのまま。

依存は optional の `[font]`（fonttools + brotli）。`embed_font='/path/font.ttf'` で
元フォントを明示指定、`True` なら IPAex明朝／Noto CJK 等を自動探索します。

## ライセンス

コードはMIT。青空文庫の収録ファイル・図書カードメタデータ（CC BY 4.0）の利用は
[取り扱い規準](https://www.aozora.gr.jp/guide/kijyunn.html)に従ってください。
