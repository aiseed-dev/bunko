/// 図書カードの中身（書誌・底本・工作員・作家）—— 共用ウィジェット。
///
/// 図書カード画面（narrow）と、読書画面の左サイドバー（デスクトップ）の
/// 両方から使う。card列のJSONを描き、未取得ならミラーから取得して保存
/// （CC BY 4.0・以後オフライン）。compact=true でサイドバー向けの詰めた組み。
library;

import 'package:flutter/material.dart';

import '../data/db.dart';
import '../data/fetch.dart';
import '../data/models.dart';
import '../theme.dart';

class CardView extends StatefulWidget {
  final WorkMeta work;
  final BunkoDb db;
  final Fetcher fetcher;
  final bool compact; // サイドバー向け（ラベル幅・字sizeを詰める）
  final bool showHeader; // 題名・作者ブロックを含めるか
  const CardView(
      {super.key,
      required this.work,
      required this.db,
      required this.fetcher,
      this.compact = false,
      this.showHeader = false});

  @override
  State<CardView> createState() => _CardViewState();
}

class _CardViewState extends State<CardView> {
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
    return ListView(
      padding: EdgeInsets.all(widget.compact ? 16 : 20),
      children: [
        if (widget.showHeader) ...[
          Text(w.title,
              style: TextStyle(
                  fontSize: widget.compact ? 18 : 26,
                  fontWeight: FontWeight.w600,
                  height: 1.4)),
          Text(w.titleYomi,
              style: const TextStyle(color: Sumi.muted, fontSize: 12)),
          const SizedBox(height: 4),
          Text('${w.author}（${w.authorYomi}）',
              style: TextStyle(
                  fontSize: widget.compact ? 13 : 15, color: Sumi.inkSoft)),
          const SizedBox(height: 8),
        ],
        if (_card == null && _error == null)
          const Padding(
              padding: EdgeInsets.all(12),
              child: Text('図書カードを取得しています…',
                  style: TextStyle(color: Sumi.muted, fontSize: 12))),
        if (_error != null)
          const Text('詳細情報はオフラインのため表示できません',
              style: TextStyle(color: Sumi.muted, fontSize: 13)),
        if (_card != null) ...cardSections(_card!, compact: widget.compact),
      ],
    );
  }
}

/// カードJSON → セクション（作品・底本・工作員・作家）のウィジェット列。
List<Widget> cardSections(Map<String, dynamic> c, {bool compact = false}) {
  final labelW = compact ? 82.0 : 110.0;
  final vSize = compact ? 12.5 : 14.0;

  Widget section(String title, List<Widget> children) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Divider(height: compact ? 24 : 32),
          Text(title,
              style: TextStyle(
                  color: Sumi.shu,
                  fontSize: compact ? 12 : 14,
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
              width: labelW,
              child: Text(k,
                  style: TextStyle(
                      color: Sumi.muted, fontSize: compact ? 11 : 13))),
          Expanded(child: Text(v, style: TextStyle(fontSize: vSize))),
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
                style: TextStyle(
                    fontSize: compact ? 12 : 13,
                    color: Sumi.inkSoft,
                    height: 1.7)),
          ),
      ],
    ]));
  }
  return out;
}
