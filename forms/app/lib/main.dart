import 'package:flutter/material.dart';
import 'package:sqflite/sqflite.dart';

import 'backup.dart';
import 'db.dart';
import 'screens/list_screen.dart';
import 'screens/settings_screen.dart';

void main() {
  runApp(const FormRescueApp());
}

class FormRescueApp extends StatelessWidget {
  const FormRescueApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'FormRescue',
      theme: ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: Colors.teal)),
      home: const _Startup(),
    );
  }
}

class _Startup extends StatefulWidget {
  const _Startup();

  @override
  State<_Startup> createState() => _StartupState();
}

class _StartupState extends State<_Startup> {
  late Future<Widget> _home;

  @override
  void initState() {
    super.initState();
    _home = _prepare();
  }

  Future<Widget> _prepare() async {
    final db = await openAppDatabase();
    await runDailyBackupIfNeeded(db);
    final configured = await _isConfigured(db);
    if (!configured) {
      return SettingsScreen(db: db, isInitialSetup: true);
    }
    return ListScreen(db: db);
  }

  Future<bool> _isConfigured(Database db) async {
    final url = await getSetting(db, 'worker_url');
    final token = await getSetting(db, 'pull_token');
    return url != null && token != null;
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Widget>(
      future: _home,
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }
        return snapshot.data!;
      },
    );
  }
}
