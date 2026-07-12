/// 文庫（dev.aiseed.bunko）—— 青空文庫を第一の蔵書とするオフライン読書アプリ。
///
/// サーバなし。同梱の aozora.db（書架メタ＋一部本文/図書カード）と
/// IPAex明朝（JIS X 0213全外字入り）だけで動き、未取得の本文は
/// GitHubミラーから読者の手元に取得する（以後オフライン）。
/// 設計は docs/DESIGN.md（正本はテキスト・Unicodeが一次表現）。
library;

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'data/aozora_parser.dart';
import 'data/db.dart';
import 'data/fetch.dart';
import 'data/sjis.dart';
import 'theme.dart';
import 'ui/shelf_page.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const BunkoApp());
}

class BunkoApp extends StatelessWidget {
  const BunkoApp({super.key});

  Future<(BunkoDb, Fetcher)> _boot() async {
    final dbBytes = await rootBundle.load('assets/aozora.db');
    final db = await BunkoDb.open(dbBytes.buffer.asUint8List());

    final cp932 = await rootBundle.load('assets/cp932.bin');
    final sjis = SjisDecoder(cp932);

    final jisJson = await rootBundle.loadString('assets/jis2ucs.json');
    final parser = AozoraParser(
        (jsonDecode(jisJson) as Map<String, dynamic>).cast<String, String>());

    return (db, Fetcher(db: db, parser: parser, sjis: sjis));
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AISeed文庫',
      theme: bunkoTheme(),
      debugShowCheckedModeBanner: false,
      home: FutureBuilder(
        future: _boot(),
        builder: (context, snap) {
          if (snap.hasError) {
            return Scaffold(
                body: Center(child: Text('起動に失敗しました\n${snap.error}')));
          }
          if (!snap.hasData) {
            return const Scaffold(
              body: Center(
                child: Column(mainAxisSize: MainAxisSize.min, children: [
                  Text('AISeed文庫',
                      style: TextStyle(
                          fontSize: 42,
                          fontWeight: FontWeight.w600,
                          color: Sumi.shu)),
                  SizedBox(height: 16),
                  CircularProgressIndicator(color: Sumi.shu),
                  SizedBox(height: 12),
                  Text('書架を開いています…',
                      style: TextStyle(color: Sumi.muted)),
                ]),
              ),
            );
          }
          final (db, fetcher) = snap.data!;
          return ShelfPage(db: db, fetcher: fetcher);
        },
      ),
    );
  }
}
