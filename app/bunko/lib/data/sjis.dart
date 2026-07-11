/// Shift_JIS (cp932) → Unicode デコーダ。
///
/// 復号表は assets/cp932.bin（uint16 LE × 65536 = 128KB。Python の cp932
/// コーデックから生成）。青空文庫の注記付きテキストを端末上で直接読むための
/// 最小実装 —— これで「正本 zip → Unicode」がアプリ内で完結する。
library;

import 'dart:typed_data';

class SjisDecoder {
  final Uint16List _table;

  SjisDecoder(ByteData table)
      : _table = table.buffer.asUint16List(table.offsetInBytes, 65536);

  static const _replacement = 0xFFFD;

  String decode(Uint8List bytes) {
    final out = StringBuffer();
    var i = 0;
    while (i < bytes.length) {
      final b = bytes[i];
      final isLead = (b >= 0x81 && b <= 0x9F) || (b >= 0xE0 && b <= 0xFC);
      if (isLead && i + 1 < bytes.length) {
        final cp = _table[(b << 8) | bytes[i + 1]];
        out.writeCharCode(cp != 0 ? cp : _replacement);
        i += 2;
      } else {
        final cp = _table[b];
        out.writeCharCode(cp != 0 || b == 0 ? cp : _replacement);
        i += 1;
      }
    }
    return out.toString();
  }
}
