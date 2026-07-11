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
| 羅生門 | 〜99%（微差） |
| 外字を含む作品（山月記・こころ 等） | 〜80-92%（下記） |

**既知の差分（次の反復）**: 公式HTMLは第3・第4水準の外字を `<img class="gaiji">` として
埋め込みます（生成当時のポリシー）。aozorabunko は外字をUnicode文字に解決するため、
外字を含む作品では画像タグとの差が出ます。pyaozora 側で公式の外字画像モードを
再現するのが次の課題です。

## ライセンス

コードはMIT。青空文庫の収録ファイル・図書カードメタデータ（CC BY 4.0）の利用は
[取り扱い規準](https://www.aozora.gr.jp/guide/kijyunn.html)に従ってください。
