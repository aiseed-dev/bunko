/// ネイティブ（Linux/Android/iOS/macOS/Windows）用の SQLite オープン。
///
/// 同梱の aozora.db をアプリサポートディレクトリへ展開して開く。
/// 以後ユーザーが取得した本文（doc列）はこのファイルに永続する。
///
/// 同梱DBのスキーマが新しくなったとき（例: ndc・reading_corpus 列の追加）は、
/// ローカルコピーを検査して作り直す。その際、ユーザーが取得済みの
/// doc/card は旧ファイルから引き継ぐ（読書キャッシュを失わせない）。
library;

import 'dart:io';
import 'dart:typed_data';

import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:sqlite3/common.dart';
import 'package:sqlite3/sqlite3.dart';

/// ローカルコピーに必須の列。同梱DBの列を増やしたらここにも足す。
const _requiredColumns = {'ndc', 'reading_corpus'};

Future<CommonDatabase> openPlatformDatabase(Uint8List assetBytes) async {
  final dir = await getApplicationSupportDirectory();
  final file = File(p.join(dir.path, 'aozora.db'));
  if (!file.existsSync()) {
    await file.create(recursive: true);
    await file.writeAsBytes(assetBytes, flush: true);
    return sqlite3.open(file.path);
  }

  var db = sqlite3.open(file.path);
  final cols = {
    for (final r in db.select('PRAGMA table_info(works)')) r['name'] as String
  };
  if (cols.containsAll(_requiredColumns)) return db;

  // 旧スキーマ: 新しい同梱DBに差し替え、取得済み doc/card を引き継ぐ
  db.close();
  final old = File('${file.path}.old');
  if (old.existsSync()) old.deleteSync();
  file.renameSync(old.path);
  await file.writeAsBytes(assetBytes, flush: true);
  db = sqlite3.open(file.path);
  try {
    db.execute("ATTACH DATABASE '${old.path}' AS old");
    db.execute('''
      UPDATE works SET
        doc  = (SELECT o.doc  FROM old.works o WHERE o.work_id = works.work_id),
        card = (SELECT o.card FROM old.works o WHERE o.work_id = works.work_id)
      WHERE EXISTS (SELECT 1 FROM old.works o
                    WHERE o.work_id = works.work_id
                      AND (o.doc IS NOT NULL OR o.card IS NOT NULL))
    ''');
    db.execute('DETACH DATABASE old');
    old.deleteSync();
  } catch (_) {
    // 引き継ぎに失敗しても新DBはそのまま使える（キャッシュは再取得可能）
  }
  return db;
}
