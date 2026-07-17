import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

const _createContact = '''
CREATE TABLE IF NOT EXISTS contact (
  remote_id INTEGER PRIMARY KEY,
  pulled_at TEXT NOT NULL DEFAULT (datetime('now')),
  created_at TEXT NOT NULL,
  email TEXT,
  payload TEXT NOT NULL,
  confirmed INTEGER NOT NULL DEFAULT 0,
  handled INTEGER NOT NULL DEFAULT 0
)
''';

const _createSettings = '''
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
)
''';

Future<Directory> dataDirectory() async {
  final docs = await getApplicationSupportDirectory();
  final dir = Directory(p.join(docs.path, 'data'));
  if (!await dir.exists()) {
    await dir.create(recursive: true);
  }
  return dir;
}

Future<Database> openAppDatabase() async {
  if (!kIsWeb &&
      (Platform.isLinux || Platform.isWindows || Platform.isMacOS)) {
    sqfliteFfiInit();
    // The isolate-backed factory can hang under some sandboxed/restricted
    // environments; this app only ever runs one query at a time, so the
    // no-isolate variant (synchronous, same-isolate) is simpler and safer.
    databaseFactory = databaseFactoryFfiNoIsolate;
  }
  final dir = await dataDirectory();
  final path = p.join(dir.path, 'inbox.db');
  return openDatabase(
    path,
    version: 1,
    onCreate: (db, version) async {
      await db.execute(_createContact);
      await db.execute(_createSettings);
    },
  );
}

Future<String?> getSetting(Database db, String key) async {
  final rows = await db.query(
    'settings',
    where: 'key = ?',
    whereArgs: [key],
    limit: 1,
  );
  if (rows.isEmpty) return null;
  return rows.first['value'] as String?;
}

Future<void> setSetting(Database db, String key, String value) async {
  await db.insert(
    'settings',
    {'key': key, 'value': value},
    conflictAlgorithm: ConflictAlgorithm.replace,
  );
}
