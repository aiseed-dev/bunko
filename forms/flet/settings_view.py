"""Settings screen: Worker URL / PULL_TOKEN via QR scan or manual entry.

deploy.py encodes the QR payload as `{"url": "...", "token": "..."}` -- see
README.md for the exact contract this screen expects.
"""

from __future__ import annotations

import json
import sqlite3

import flet as ft

from db import get_setting, set_setting


def qr_scan_supported() -> bool:
    # flet-camera only ships a native preview on Android/iOS (see its own
    # platform-support table); everywhere else falls back to manual entry.
    platform = ft.context.page.platform
    return platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)


@ft.component
def QrScanPanel(on_result, on_cancel):
    import flet_camera as fc

    camera_ref = ft.use_ref(lambda: fc.Camera(expand=True, preview_enabled=True))
    status, set_status = ft.use_state("カメラを準備しています...")
    busy, set_busy = ft.use_state(False)

    async def setup():
        from flet_camera.types import CameraLensDirection, ResolutionPreset

        try:
            cameras = await camera_ref.current.get_available_cameras()
            back = next(
                (c for c in cameras if c.lens_direction == CameraLensDirection.BACK),
                cameras[0] if cameras else None,
            )
            if back is None:
                set_status("使用できるカメラが見つかりません")
                return
            await camera_ref.current.initialize(
                description=back,
                resolution_preset=ResolutionPreset.MEDIUM,
                enable_audio=False,
            )
            set_status("QRコードを枠内に収めて撮影してください")
        except Exception as e:
            set_status(f"カメラの初期化に失敗しました: {e}")

    ft.use_effect(setup, dependencies=[])

    async def capture(e):
        from qr import decode_qr

        set_busy(True)
        try:
            data = await camera_ref.current.take_picture()
            text = decode_qr(data)
            if text is None:
                set_status("QRコードを認識できませんでした。もう一度お試しください")
            else:
                on_result(text)
        except Exception as ex:
            set_status(f"読み取りに失敗しました: {ex}")
        finally:
            set_busy(False)

    return ft.Column(
        [
            ft.Container(content=camera_ref.current, height=400),
            ft.Text(status),
            ft.Row(
                [
                    ft.FilledButton(
                        "撮影して読み取る", disabled=busy, on_click=capture
                    ),
                    ft.TextButton("キャンセル", on_click=lambda e: on_cancel()),
                ]
            ),
        ],
        spacing=12,
    )


@ft.component
def SettingsView(
    conn: sqlite3.Connection,
    on_saved,
    on_cancel=None,
    on_help=None,
    is_initial_setup: bool = False,
):
    url, set_url = ft.use_state(get_setting(conn, "worker_url") or "")
    token, set_token = ft.use_state(get_setting(conn, "pull_token") or "")
    error, set_error = ft.use_state("")
    saving, set_saving = ft.use_state(False)
    scanning, set_scanning = ft.use_state(False)

    def apply_qr_result(text: str) -> None:
        try:
            data = json.loads(text)
            new_url = data.get("url")
            new_token = data.get("token")
            if not new_url or not new_token:
                raise ValueError("url/token が見つかりません")
            if not new_url.startswith("https://"):
                raise ValueError("URLはhttps://で始まる必要があります")
            set_url(new_url)
            set_token(new_token)
            set_error("")
        except Exception as e:
            set_error(f"QRの読み取りに失敗しました: {e}")
        set_scanning(False)

    def save(e) -> None:
        u = url.strip()
        t = token.strip()
        if not u or not t:
            set_error("Worker URLとPULL_TOKENの両方を入力してください")
            return
        if not u.startswith("https://"):
            set_error("URLはhttps://で始まる必要があります")
            return
        set_saving(True)
        set_error("")
        normalized = u[:-1] if u.endswith("/") else u
        set_setting(conn, "worker_url", normalized)
        set_setting(conn, "pull_token", t)
        set_saving(False)
        on_saved()

    if scanning:
        return QrScanPanel(
            on_result=apply_qr_result, on_cancel=lambda: set_scanning(False)
        )

    if is_initial_setup:
        qr_note = (
            "deploy.py が表示したQRコードを下のボタンから読み取ると、"
            "二つとも自動で入力されます。"
            if qr_scan_supported()
            else "deploy.py の出力から Worker URL と PULL_TOKEN をコピーして、"
            "下の欄に貼り付けてください。"
            "(QRコードでの読み取りは Android/iOS 版で使えます)"
        )
        header = ft.Column(
            [
                ft.Text("FormRescue へようこそ", size=22, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "FormRescue は、WordPressの問い合わせフォームに届いたデータを、"
                    "Cloudflare上の受信箱から引き取って手元で管理するアプリです。"
                    "データはこの端末の中にだけ保存されます。"
                ),
                ft.Text(
                    "はじめるには、受信箱を設置したとき(deploy.py または "
                    "cf-publish の実行時)に表示された Worker URL と PULL_TOKEN "
                    "を設定します。手元にない場合は、受信箱を設置した人に確認して"
                    "ください。"
                ),
                ft.Text(qr_note),
                ft.TextButton(
                    "詳しい説明を見る",
                    icon=ft.Icons.HELP_OUTLINE,
                    on_click=lambda e: on_help(),
                )
                if on_help is not None
                else ft.Container(),
                ft.Divider(),
            ],
            spacing=10,
        )
    else:
        header = None
    scan_button = (
        ft.FilledButton(
            "QRコードを読み取る",
            icon=ft.Icons.QR_CODE_SCANNER,
            on_click=lambda e: set_scanning(True),
        )
        if qr_scan_supported()
        else None
    )
    error_text = (
        ft.Text(error, color=ft.Colors.ERROR) if error else None
    )

    actions = [
        ft.FilledButton(
            "保存中..." if saving else "保存", disabled=saving, on_click=save
        ),
    ]
    if on_cancel is not None:
        actions.append(ft.TextButton("戻る", on_click=lambda e: on_cancel()))

    controls = [
        ft.Text("設定", size=22, weight=ft.FontWeight.BOLD)
        if not is_initial_setup
        else None,
        header,
        scan_button,
        ft.TextField(
            label="Worker URL",
            hint_text="https://xxxx.workers.dev",
            value=url,
            on_change=lambda e: set_url(e.control.value),
        ),
        ft.TextField(
            label="PULL_TOKEN",
            value=token,
            password=True,
            can_reveal_password=True,
            on_change=lambda e: set_token(e.control.value),
        ),
        error_text,
        ft.Row(actions),
    ]
    return ft.Column(
        [c for c in controls if c is not None],
        spacing=12,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )
