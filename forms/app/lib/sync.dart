import 'package:sqflite/sqflite.dart';

import 'api.dart';

Future<int> pullItems(Database db, ApiConfig config) async {
  // Start after the highest remote_id we already hold, then page forward until
  // a short page signals the inbox is drained. This survives an inbox far
  // larger than one response, since /items caps each page at itemsPageLimit.
  final row = (await db.rawQuery(
    'SELECT MAX(remote_id) AS m FROM contact',
  )).first;
  var after = (row['m'] as int?) ?? 0;
  var inserted = 0;

  while (true) {
    final page = await fetchItemsPage(config, after: after);
    if (page.isEmpty) break;

    final batch = db.batch();
    for (final item in page) {
      batch.insert(
        'contact',
        {
          'remote_id': item.id,
          'created_at': item.createdAt,
          'email': item.email,
          'payload': item.payload,
        },
        conflictAlgorithm: ConflictAlgorithm.ignore,
      );
    }
    final results = await batch.commit(noResult: false);
    for (final r in results) {
      if (r is int && r > 0) inserted++;
    }

    after = page.last.id;
    if (page.length < itemsPageLimit) break;
  }
  return inserted;
}
