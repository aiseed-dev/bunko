/// 図書カード —— 狭い画面用の単独ページ（中身は CardView に共通化）。
/// デスクトップでは読書画面の左サイドバーとして同じ内容が出る。
library;

import 'package:flutter/material.dart';

import '../data/db.dart';
import '../data/fetch.dart';
import '../data/models.dart';
import '../theme.dart';
import 'card_view.dart';
import 'reader_page.dart';

class CardPage extends StatelessWidget {
  final WorkMeta work;
  final BunkoDb db;
  final Fetcher fetcher;
  const CardPage(
      {super.key, required this.work, required this.db, required this.fetcher});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('図書カード')),
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(work.title,
                    style: const TextStyle(
                        fontSize: 26, fontWeight: FontWeight.w600,
                        height: 1.4)),
                Text(work.titleYomi,
                    style: const TextStyle(color: Sumi.muted)),
                const SizedBox(height: 4),
                Text('${work.author}（${work.authorYomi}）',
                    style:
                        const TextStyle(fontSize: 15, color: Sumi.inkSoft)),
                const SizedBox(height: 16),
                FilledButton.icon(
                  style: FilledButton.styleFrom(
                      backgroundColor: Sumi.shu,
                      padding: const EdgeInsets.symmetric(vertical: 14)),
                  icon: const Icon(Icons.menu_book),
                  label: Text(work.hasDoc ? '読む（取得済み）' : '読む'),
                  onPressed: () => Navigator.of(context).push(
                      MaterialPageRoute(
                          builder: (_) => ReaderPage(
                              work: work, db: db, fetcher: fetcher))),
                ),
              ]),
        ),
        Expanded(child: CardView(work: work, db: db, fetcher: fetcher)),
      ]),
    );
  }
}
