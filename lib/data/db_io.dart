/// ネイティブ（Linux/Android/iOS/macOS/Windows）用の SQLite オープン。
///
/// 同梱の aozora.db をアプリサポートディレクトリへ一度だけ展開して開く。
/// 以後ユーザーが取得した本文（doc列）はこのファイルに永続する。
library;

import 'dart:io';
import 'dart:typed_data';

import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:sqlite3/common.dart';
import 'package:sqlite3/sqlite3.dart';

Future<CommonDatabase> openPlatformDatabase(Uint8List assetBytes) async {
  final dir = await getApplicationSupportDirectory();
  final file = File(p.join(dir.path, 'aozora.db'));
  if (!file.existsSync()) {
    await file.create(recursive: true);
    await file.writeAsBytes(assetBytes, flush: true);
  }
  return sqlite3.open(file.path);
}
