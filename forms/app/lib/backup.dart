import 'dart:io';

import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';

import 'db.dart';

const _keepDays = 30;

String _dateStamp(DateTime d) {
  final y = d.year.toString().padLeft(4, '0');
  final m = d.month.toString().padLeft(2, '0');
  final day = d.day.toString().padLeft(2, '0');
  return '$y$m$day';
}

/// Copies inbox.db to a dated backup once per day, then prunes backups
/// older than [_keepDays] days. Safe to call every app start.
Future<void> runDailyBackupIfNeeded(Database db) async {
  final today = _dateStamp(DateTime.now());
  final lastBackup = await getSetting(db, 'last_backup_date');
  if (lastBackup == today) return;

  final dataDir = await dataDirectory();
  final dbFile = File(p.join(dataDir.path, 'inbox.db'));
  if (!await dbFile.exists()) return;

  final backupDir = Directory(p.join(dataDir.parent.path, 'backups'));
  if (!await backupDir.exists()) {
    await backupDir.create(recursive: true);
  }
  final backupFile = File(p.join(backupDir.path, 'inbox-$today.db'));
  await dbFile.copy(backupFile.path);

  final cutoff = DateTime.now().subtract(const Duration(days: _keepDays));
  await for (final entity in backupDir.list()) {
    if (entity is! File) continue;
    final stat = await entity.stat();
    if (stat.modified.isBefore(cutoff)) {
      await entity.delete();
    }
  }

  await setSetting(db, 'last_backup_date', today);
}
