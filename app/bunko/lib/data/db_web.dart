/// Web（Flutter Web / wasm）用の SQLite オープン。
///
/// web/sqlite3.wasm をロードし、同梱 aozora.db をインメモリVFSに展開して開く。
/// （Web版はセッション内メモリ。永続化はIndexedDB VFS導入で将来対応）
library;

import 'dart:typed_data';

import 'package:sqlite3/wasm.dart';
import 'package:typed_data/typed_buffers.dart';

Future<CommonDatabase> openPlatformDatabase(Uint8List assetBytes) async {
  final sqlite = await WasmSqlite3.loadFromUrl(Uri.parse('sqlite3.wasm'));
  final fs = InMemoryFileSystem();
  sqlite.registerVirtualFileSystem(fs, makeDefault: true);
  fs.fileData['/aozora.db'] = Uint8Buffer()..addAll(assetBytes);
  return sqlite.open('/aozora.db');
}
