/// 図書カード —— 書誌・底本・工作員（入力/校正）・作家。card列のJSONを描く。
/// 未取得ならミラーから取得してcard列へ保存（CC BY 4.0・以後オフライン）。
library;

import 'package:flutter/material.dart';

import '../data/db.dart';
import '../data/fetch.dart';
import '../data/models.dart';
import '../theme.dart';
import 'reader_page.dart';

class CardPage extends StatefulWidget {
  final WorkMeta work;
  final BunkoDb db;
  final Fetcher fetcher;
  const CardPage(
      {super.key, required this.work, required this.db, required this.fetcher});

  @override
  State<CardPage> createState() => _CardPageState();
}

class _CardPageState extends State<CardPage> {
  Map<String, dynamic>? _card;
  String? _error;

  @override
  void initState() {
    super.initState();
    _card = widget.db.loadCard(widget.work.workId);
    if (_card == null) _fetch();
  }

  Future<void> _fetch() async {
    try {
      final c = await widget.fetcher.fetchCard(widget.work);
      if (mounted) setState(() => _card = c);
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    }
  }

  @override
  Widget build(BuildContext context) {
    final w = widget.work;
    return Scaffold(
      appBar: AppBar(title: const Text('図書カード')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Text(w.title,
              style: const TextStyle(
                  fontSize: 26, fontWeight: FontWeight.w600, height: 1.4)),
          Text(w.titleYomi, style: const TextStyle(color: Sumi.muted)),
          const SizedBox(height: 4),
          Text('${w.author}（${w.authorYomi}）',
              style: const TextStyle(fontSize: 15, color: Sumi.inkSoft)),
          const SizedBox(height: 16),
          FilledButton.icon(
            style: FilledButton.styleFrom(
                backgroundColor: Sumi.shu,
                padding: const EdgeInsets.symmetric(vertical: 14)),
            icon: const Icon(Icons.menu_book),
            label: Text(w.hasDoc ? '読む（取得済み）' : '読む'),
            onPressed: () => Navigator.of(context).push(MaterialPageRoute(
                builder: (_) => ReaderPage(
                    work: w, db: widget.db, fetcher: widget.fetcher))),
          ),
          const SizedBox(height: 20),
          if (_card == null && _error == null)
            const Center(
                child: Padding(
                    padding: EdgeInsets.all(12),
                    child: Text('図書カードを取得しています…',
                        style: TextStyle(color: Sumi.muted)))),
          if (_error != null)
            Text('詳細情報はオフラインのため表示できません',
                style: const TextStyle(color: Sumi.muted, fontSize: 13)),
          if (_card != null) ..._cardSections(_card!),
        ],
      ),
    );
  }

  List<Widget> _cardSections(Map<String, dynamic> c) {
    Widget section(String title, List<Widget> children) => Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Divider(height: 32),
            Text(title,
                style: const TextStyle(
                    color: Sumi.shu,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 2)),
            const SizedBox(height: 8),
            ...children,
          ],
        );

    Widget kv(String k, String v) => Padding(
          padding: const EdgeInsets.only(bottom: 4),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            SizedBox(
                width: 110,
                child:
                    Text(k, style: const TextStyle(color: Sumi.muted, fontSize: 13))),
            Expanded(child: Text(v, style: const TextStyle(fontSize: 14))),
          ]),
        );

    final out = <Widget>[];
    final work = (c['work'] as Map?)?.cast<String, dynamic>() ?? {};
    final interesting = ['分類', '初出', '文字遣い種別', '作品について'];
    final workRows = [
      for (final k in interesting)
        if (work[k] != null && '${work[k]}'.isNotEmpty) kv(k, '${work[k]}')
    ];
    if (workRows.isNotEmpty) out.add(section('作品', workRows));

    final books = (c['books'] as List?) ?? [];
    if (books.isNotEmpty) {
      out.add(section('底本', [
        for (final b in books.cast<Map>())
          kv('${b['role'] ?? '底本'}',
              [
                '${b['名称'] ?? ''}',
                if ((b['出版社'] ?? '') != '') '${b['出版社']}',
                if ((b['初版発行日'] ?? '') != '') '${b['初版発行日']}',
              ].join('　')),
      ]));
    }

    final staff = (c['staff'] as Map?)?.cast<String, dynamic>() ?? {};
    if (staff.isNotEmpty) {
      out.add(section('工作員（この本を届けた人）', [
        for (final e in staff.entries) kv(e.key, '${e.value}'),
      ]));
    }

    final authors = (c['authors'] as List?) ?? [];
    if (authors.isNotEmpty) {
      out.add(section('作家', [
        for (final a in authors.cast<Map>()) ...[
          kv('${a['分類'] ?? '著者'}',
              '${a['作家名'] ?? ''}（${a['作家名読み'] ?? ''}）'),
          if ((a['生年'] ?? '') != '')
            kv('生没年', '${a['生年']} 〜 ${a['没年'] ?? ''}'),
          if ((a['人物について'] ?? '') != '')
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text('${a['人物について']}',
                  style: const TextStyle(
                      fontSize: 13, color: Sumi.inkSoft, height: 1.7)),
            ),
        ],
      ]));
    }
    return out;
  }
}
