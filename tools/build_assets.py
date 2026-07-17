# -*- coding: utf-8 -*-
"""bunko データ資産の生成（tools/ から実行: python tools/build_assets.py）
- assets/aozora.db      … 全メタ＋代表作の doc/card JSON 充填
- assets/jis2ucs.json   … 外字表（面区点→Unicode。静的ビューア等の非Python消費者用）
- assets/cp932.bin      … Shift_JIS(cp932)→Unicode 復号表（uint16 LE ×65536 = 128KB）
- assets/fonts/         … IPAex明朝（本文＋全外字を1フォントで）
"""
import json, pathlib, shutil, struct, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent  # bunko リポルート
ASSETS = ROOT / "assets"   # データ資産の置き場
(ASSETS / "fonts").mkdir(parents=True, exist_ok=True)

# 1) cp932 復号表 ------------------------------------------------------
tbl = bytearray(65536 * 2)
# 1バイト文字（0x00-0xFF のうち cp932 で単独有効なもの）
for b in range(256):
    try:
        ch = bytes([b]).decode("cp932")
        cp = ord(ch)
        if cp <= 0xFFFF:
            struct.pack_into("<H", tbl, b * 2, cp)
    except Exception:
        pass
# 2バイト文字
n2 = 0
for lead in list(range(0x81, 0xA0)) + list(range(0xE0, 0xFD)):
    for trail in range(0x40, 0xFD):
        if trail == 0x7F:
            continue
        try:
            ch = bytes([lead, trail]).decode("cp932")
            cp = ord(ch)
            if cp <= 0xFFFF:
                struct.pack_into("<H", tbl, (lead << 8 | trail) * 2, cp)
                n2 += 1
        except Exception:
            pass
(ASSETS / "cp932.bin").write_bytes(tbl)
print(f"cp932.bin: {len(tbl)} bytes / 2byte文字 {n2}")

# 2) 外字表 -----------------------------------------------------------
src = ROOT / "pybunko" / "data" / "jis2ucs.json"
shutil.copy(src, ASSETS / "jis2ucs.json")
print("jis2ucs.json:", (ASSETS/"jis2ucs.json").stat().st_size, "bytes")

# 3) フォント ---------------------------------------------------------
font_src = pathlib.Path("/usr/share/fonts/opentype/ipaexfont-mincho/ipaexm.ttf")
shutil.copy(font_src, ASSETS / "fonts" / "ipaexm.ttf")
lic = pathlib.Path("/usr/share/doc/fonts-ipaexfont-mincho/copyright")
if lic.exists():
    shutil.copy(lic, ASSETS / "fonts" / "IPA_Font_License.txt")
else:
    (ASSETS/"fonts"/"IPA_Font_License.txt").write_text(
        "IPAex Mincho — IPA Font License Agreement v1.0\n"
        "https://moji.or.jp/ipafont/license/\n", encoding="utf-8")
print("font:", (ASSETS/"fonts"/"ipaexm.ttf").stat().st_size, "bytes")

# 4) aozora.db（全メタ＋代表作の doc/card）------------------------------
from pybunko import Library, db
cache = pathlib.Path(tempfile.mkdtemp(prefix="bunko-assets-"))
lib = Library(cache_dir=cache)
dbp = str(ASSETS / "aozora.db")
lib.build_sqlite(dbp)      # 全メタ（~1秒）

STARTERS = ["走れメロス", "山月記", "羅生門", "吾輩は猫である", "こころ", "坊っちゃん",
            "銀河鉄道の夜", "注文の多い料理店", "セロ弾きのゴーシュ", "人間失格",
            "蜘蛛の糸", "地獄変", "鼻", "変身", "高瀬舟", "檸檬", "桜の樹の下には",
            "風の又三郎", "よだかの星", "杜子春", "トロッコ", "草枕", "夢十夜",
            "斜陽", "駈込み訴え", "女生徒", "永訣の朝", "山椒魚", "小僧の神様", "城の崎にて"]
ok, ng = 0, []
docs, cards = [], []
for t in STARTERS:
    try:
        hits = lib.search(t)
        w = hits[0]
        docs.append((w.work_id, w.document().to_dict()))
        try:
            cards.append((w.work_id, w.card()))
        except Exception:
            pass
        ok += 1
    except Exception as e:
        ng.append((t, type(e).__name__))
db.store_documents(dbp, docs)
db.store_cards(dbp, cards)
st = db.stats(dbp)
print(f"aozora.db: {pathlib.Path(dbp).stat().st_size/1024/1024:.1f} MB  stats={st}  取得失敗={ng}")

# 5) NDL読みコーパスのフラグ（reading_corpus 列） --------------------------
from pybunko.ndl import mark_reading_corpus
n = mark_reading_corpus(dbp)
print(f"読みコーパスあり: {n} 作品（NDL hurigana-speech-corpus-aozora）")
