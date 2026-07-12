/// db_io の旧ローカルDB移行（スキーマ更新＋doc/card引き継ぎ）のテスト。
@TestOn('vm')
library;

import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:sqlite3/sqlite3.dart';

import 'package:bunko/data/db_io.dart';
import 'package:path_provider_platform_interface/path_provider_platform_interface.dart';

class _FakePathProvider extends PathProviderPlatform {
  final String path;
  _FakePathProvider(this.path);
  @override
  Future<String?> getApplicationSupportPath() async => path;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('旧スキーマのローカルDBは差し替えられ、doc/cardが引き継がれる', () async {
    final tmp = Directory.systemTemp.createTempSync('bunko_db_test');
    PathProviderPlatform.instance = _FakePathProvider(tmp.path);

    // 新スキーマの「同梱DB」（ndc・reading_corpus あり・docなし）
    final assetFile = File('${tmp.path}/asset.db');
    final assetDb = sqlite3.open(assetFile.path);
    assetDb.execute('''
      CREATE TABLE works (work_id TEXT PRIMARY KEY, title TEXT,
        title_yomi TEXT, author TEXT, author_yomi TEXT, row TEXT,
        card_url TEXT, text_url TEXT, copyrighted INTEGER,
        ndc TEXT, reading_corpus INTEGER NOT NULL DEFAULT 0,
        doc TEXT, card TEXT)''');
    assetDb.execute(
        "INSERT INTO works (work_id,title,ndc) VALUES ('001','作品','913')");
    assetDb.close();
    final assetBytes = Uint8List.fromList(assetFile.readAsBytesSync());

    // 旧スキーマのローカルDB（ndc無し・取得済みdocあり）
    final oldFile = File('${tmp.path}/aozora.db');
    final oldDb = sqlite3.open(oldFile.path);
    oldDb.execute('''
      CREATE TABLE works (work_id TEXT PRIMARY KEY, title TEXT, doc TEXT,
        card TEXT)''');
    oldDb.execute(
        "INSERT INTO works VALUES ('001','作品','{\"cached\":true}','{}')");
    oldDb.close();

    final db = await openPlatformDatabase(assetBytes);
    final row = db.select('SELECT ndc, doc FROM works WHERE work_id=?', ['001']).first;
    expect(row['ndc'], '913'); // 新スキーマになった
    expect(row['doc'], '{"cached":true}'); // キャッシュは引き継がれた
    expect(File('${tmp.path}/aozora.db.old').existsSync(), false);
    db.close();
    tmp.deleteSync(recursive: true);
  });
}
