"""main.py — AISeed工房の入口（`flet run` はこのファイルを探す）。

デスクトップ:  flet run          （または python main.py）
Web/スマフォ:  KOBO_PORT=8790 python main.py
              → PC: http://localhost:8790 ／ 同一LANのスマフォからも開ける

アプリ本体（6タブ: 執筆・入力・校正・検査・資産・検証）は aozora_kobo.py。
"""
import os
import shutil
from pathlib import Path

import flet as ft

from aozora_kobo import main as app

# 同梱フォント（IPAex明朝・外字込み）を assets/ に用意する。
# リポジトリ共有の assets/fonts から実コピー（シンボリックリンクはStaticFilesが辿らない）。
_font = Path(__file__).parent / 'assets' / 'fonts' / 'ipaexm.ttf'
if not _font.exists():
    src = Path(__file__).parent / '..' / '..' / 'assets' / 'fonts' / 'ipaexm.ttf'
    _font.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src.resolve(), _font)

port = int(os.environ.get('KOBO_PORT', '0'))
if port:  # Webサーバとして起動（スマフォ・別PCから使う）
    ft.run(app, port=port, view=ft.AppView.WEB_BROWSER,
           host=os.environ.get('KOBO_HOST', '0.0.0.0'),
           assets_dir='assets',
           web_renderer=ft.WebRenderer.CANVAS_KIT)
else:     # デスクトップアプリとして起動
    ft.run(app, assets_dir='assets')
