"""QR decoding helper. pyzbar/Pillow are only importable where flet-libzbar's
prebuilt binary is available (Android/iOS via pypi.flet.dev); the import is
kept lazy so desktop platforms -- which never render the camera UI -- don't
need libzbar installed at all.
"""

from __future__ import annotations

import io


def decode_qr(image_bytes: bytes) -> str | None:
    from PIL import Image
    from pyzbar.pyzbar import decode

    results = decode(Image.open(io.BytesIO(image_bytes)))
    if not results:
        return None
    return results[0].data.decode("utf-8")
