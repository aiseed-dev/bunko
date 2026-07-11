# ライセンス方針（検討と決定）

作成: 2026-07-11。名義: Copyright (C) 2026 aiseed.dev

## 全体像

| 対象 | ライセンス |
|---|---|
| **コード全般**（pybunko・工房・tools・Flutterアプリ） | **AGPL-3.0-or-later**（ルートのLICENSE） |
| app/bunko（iOS/App Store配布時） | AGPL ＋ aiseed.dev による**ストア配布用の個別許諾**（デュアル・下記） |
| **データ資産**（assets/） | **CC BY 4.0 基本**（出典: 青空文庫）＋例外（下記） |

## 1. なぜコードは AGPL か

- このプロジェクトの思想は「サーバを増やさない」だが、第三者がこのコードで
  **サービスを建てることは自由**。その場合も改良がコミュニティへ還る形
  （ネットワーク・コピーレフト）を担保したい。
- **適合性の実利**: EPUB出力が依存する `ebooklib` は **AGPL-3.0**。
  従来のMIT表記はEPUB機能を含む配布で潜在的な非適合を抱えていたが、
  AGPL採用でこの矛盾が解消される。
- その他の依存はすべてAGPLと互換: Flutter/Dartパッケージ（BSD/MIT）、
  flet（Apache-2.0）、washi-md / mdit-py-cjk-friendly（MIT・自作）。

## 2. Flutterアプリ（iOS）とデュアルライセンス

**問題**: GPL系ライセンスは Apple App Store の利用規約（追加の利用制限）と
衝突するというのが通説（VLCがストアから取り下げられた事例）。
AGPLのままでは iOS 配布に法的リスクがある。

**方針（デュアルライセンス）**:
- app/bunko のコードも既定は AGPL-3.0-or-later。
- **著作権者 aiseed.dev は、自らの著作物を App Store / Google Play 等の
  規約に適合する個別条件で配布できる**（著作権者は自分のライセンスに拘束されない）。
- **外部コントリビューションの条件**: プルリク等での貢献は
  「AGPL-3.0-or-later で提供すること」に加え、
  「aiseed.dev がアプリストア配布のために当該貢献を再許諾できること」への
  同意を含む（簡易CLA）。これにより将来もデュアル配布が維持できる。

## 3. データは CC BY 4.0 基本

- `assets/aozora.db` … 書架・図書カード由来メタデータは青空文庫の
  **CC BY 4.0**（クレジット表記:「青空文庫」）。本文（doc列）は
  パブリックドメイン作品。DB全体の再配布は **CC BY 4.0・出典明記** で。
- 収録ファイルの利用は「青空文庫収録ファイルの取り扱い規準」
  （https://www.aozora.gr.jp/guide/kijyunn.html）に従う。

**例外（データ側・各自のライセンスが優先）**:

| ファイル | ライセンス | 出典 |
|---|---|---|
| `pybunko/data/jis2ucs.json` / `accent_table.json` | CC0-1.0 | aozorahack/aozora2html |
| `assets/cp932.bin` | CC0-1.0（符号対応表＝事実データ） | Python cp932 コーデックから生成 |
| `assets/fonts/ipaexm.ttf` | **IPA Font License v1.0**（変更不可・全文同梱） | IPA |
| tests/golden の作品ファイル | パブリックドメイン（取り扱い規準に従う） | 青空文庫 |

## 4. 表記

- ルート `LICENSE` = AGPL-3.0 全文。SPDX: `AGPL-3.0-or-later`。
- pyproject: `license = { text = "AGPL-3.0-or-later" }`。
- 著作権表示: `Copyright (C) 2026 aiseed.dev`（この文書とREADMEに記載）。
