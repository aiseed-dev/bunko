import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'package:formrescue/screens/settings_screen.dart';

void main() {
  setUpAll(() {
    sqfliteFfiInit();
    // The isolate-backed factory can hang under the flutter_tester sandbox;
    // the no-isolate variant runs queries synchronously and is fine for tests.
    databaseFactory = databaseFactoryFfiNoIsolate;
  });

  testWidgets('Settings screen shows the Worker URL and PULL_TOKEN fields', (
    tester,
  ) async {
    final db = await databaseFactory.openDatabase(inMemoryDatabasePath);
    await db.execute(
      'CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)',
    );

    await tester.pumpWidget(
      MaterialApp(home: SettingsScreen(db: db, isInitialSetup: true)),
    );
    await tester.pumpAndSettle();

    expect(find.text('Worker URL'), findsOneWidget);
    expect(find.text('PULL_TOKEN'), findsOneWidget);
  });
}
