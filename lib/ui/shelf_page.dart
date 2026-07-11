/// 書架 —— 五十音行タブ＋検索。作家別作品一覧CSV由来のSQLiteメタを引くだけ。
library;

import 'package:flutter/material.dart';

import '../data/db.dart';
import '../data/fetch.dart';
import '../data/models.dart';
import '../theme.dart';
import 'card_page.dart';

const kanaRows = ['あ', 'か', 'さ', 'た', 'な', 'は', 'ま', 'や', 'ら', 'わ', 'その他'];

class ShelfPage extends StatefulWidget {
  final BunkoDb db;
  final Fetcher fetcher;
  const ShelfPage({super.key, required this.db, required this.fetcher});

  @override
  State<ShelfPage> createState() => _ShelfPageState();
}

class _ShelfPageState extends State<ShelfPage> {
  String _row = 'あ';
  String _query = '';
  late List<AuthorGroup> _authors;

  @override
  void initState() {
    super.initState();
    _authors = widget.db.authors(row: _row);
  }

  void _setRow(String row) {
    setState(() {
      _row = row;
      _authors = widget.db.authors(row: row == '全' ? null : row);
    });
  }

  @override
  Widget build(BuildContext context) {
    final st = widget.db.stats();
    return Scaffold(
      appBar: AppBar(
        titleSpacing: 20,
        title: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('文庫',
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.w600)),
          Text('青空文庫 ── ${st.authors} 作家 ／ ${st.works} 作品（手元の書架）',
              style: const TextStyle(fontSize: 11, color: Sumi.muted)),
        ]),
        toolbarHeight: 64,
      ),
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 6),
          child: TextField(
            decoration: const InputDecoration(
                hintText: '作品名・作家名・よみ で検索',
                prefixIcon: Icon(Icons.search, color: Sumi.muted)),
            onChanged: (v) => setState(() => _query = v.trim()),
          ),
        ),
        if (_query.isEmpty)
          SizedBox(
            height: 44,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              children: [
                for (final r in ['全', ...kanaRows])
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 3),
                    child: ChoiceChip(
                      label: Text(r),
                      selected: _row == r,
                      selectedColor: Sumi.shu,
                      labelStyle: TextStyle(
                          color: _row == r ? Sumi.paperHi : Sumi.inkSoft),
                      onSelected: (_) => _setRow(r),
                    ),
                  ),
              ],
            ),
          ),
        const Divider(height: 8),
        Expanded(child: _query.isEmpty ? _authorList() : _searchList()),
      ]),
    );
  }

  Widget _searchList() {
    final hits = widget.db.search(_query);
    if (hits.isEmpty) {
      return const Center(
          child: Text('見つかりませんでした', style: TextStyle(color: Sumi.muted)));
    }
    return ListView.separated(
      itemCount: hits.length,
      separatorBuilder: (c, i) => const Divider(height: 1),
      itemBuilder: (context, i) => _workTile(hits[i]),
    );
  }

  Widget _authorList() {
    return ListView.builder(
      itemCount: _authors.length,
      itemBuilder: (context, i) {
        final a = _authors[i];
        return ExpansionTile(
          shape: const Border(),
          title: Row(children: [
            Flexible(
                child: Text(a.author,
                    style: const TextStyle(fontWeight: FontWeight.w600))),
            const SizedBox(width: 8),
            Text(a.authorYomi,
                style: const TextStyle(fontSize: 11, color: Sumi.muted)),
          ]),
          trailing: Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
            decoration: BoxDecoration(
                color: Sumi.shu.withValues(alpha: .1),
                borderRadius: BorderRadius.circular(999)),
            child: Text('${a.count}',
                style: const TextStyle(color: Sumi.shu, fontSize: 12)),
          ),
          children: [
            for (final w in widget.db.byAuthor(a.author, a.authorYomi))
              _workTile(w, dense: true),
          ],
        );
      },
    );
  }

  Widget _workTile(WorkMeta w, {bool dense = false}) {
    return ListTile(
      dense: dense,
      contentPadding: EdgeInsets.only(left: dense ? 32 : 16, right: 16),
      title: Text(w.title),
      subtitle: dense
          ? null
          : Text('${w.author}　${w.titleYomi}',
              style: const TextStyle(fontSize: 12, color: Sumi.muted)),
      trailing: w.hasDoc
          ? const Icon(Icons.download_done, size: 16, color: Sumi.muted)
          : null,
      onTap: () => Navigator.of(context).push(MaterialPageRoute(
          builder: (_) =>
              CardPage(work: w, db: widget.db, fetcher: widget.fetcher))),
    );
  }
}
