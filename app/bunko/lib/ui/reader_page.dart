/// 読書画面 —— doc列のUnicodeデータを描くだけ（外字も実文字・画像も注記も無し）。
/// 横書き（ルビ上付き）と縦書き（自前レイアウト）を切替。未取得の本文は
/// ミラーから取得してdocへ保存（次回からオフライン）。
library;

import 'package:flutter/material.dart';

import '../data/db.dart';
import '../data/fetch.dart';
import '../data/models.dart';
import '../theme.dart';
import 'ruby_text.dart';
import 'vertical_reader.dart';

class ReaderPage extends StatefulWidget {
  final WorkMeta work;
  final BunkoDb db;
  final Fetcher fetcher;
  const ReaderPage(
      {super.key, required this.work, required this.db, required this.fetcher});

  @override
  State<ReaderPage> createState() => _ReaderPageState();
}

class _ReaderPageState extends State<ReaderPage> {
  late Future<Doc> _doc;
  double _fontSize = 19;
  bool _vertical = false;

  @override
  void initState() {
    super.initState();
    _doc = _load();
  }

  Future<Doc> _load() async {
    final cached = widget.db.loadDoc(widget.work.workId);
    if (cached != null) return cached;
    return widget.fetcher.fetchDoc(widget.work);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('${widget.work.title} ／ ${widget.work.author}',
            style: const TextStyle(fontSize: 16)),
        actions: [
          IconButton(
            tooltip: _vertical ? '横書きにする' : '縦書きにする',
            icon: Icon(_vertical
                ? Icons.text_rotation_none
                : Icons.text_rotate_vertical),
            onPressed: () => setState(() => _vertical = !_vertical),
          ),
          IconButton(
              tooltip: '小さく',
              icon: const Icon(Icons.text_decrease),
              onPressed: () => setState(
                  () => _fontSize = (_fontSize - 2).clamp(12, 34))),
          IconButton(
              tooltip: '大きく',
              icon: const Icon(Icons.text_increase),
              onPressed: () => setState(
                  () => _fontSize = (_fontSize + 2).clamp(12, 34))),
        ],
      ),
      body: FutureBuilder<Doc>(
        future: _doc,
        builder: (context, snap) {
          if (snap.hasError) {
            return Center(
                child: Padding(
              padding: const EdgeInsets.all(24),
              child: Text('本文を取得できませんでした。\n${snap.error}',
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Sumi.muted)),
            ));
          }
          if (!snap.hasData) {
            return const Center(
                child: Column(mainAxisSize: MainAxisSize.min, children: [
              CircularProgressIndicator(color: Sumi.shu),
              SizedBox(height: 12),
              Text('正本を取得しています…', style: TextStyle(color: Sumi.muted)),
            ]));
          }
          final doc = snap.data!;
          return _vertical
              ? Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: VerticalReader(doc: doc, fontSize: _fontSize))
              : _HorizontalReader(doc: doc, fontSize: _fontSize);
        },
      ),
    );
  }
}

class _HorizontalReader extends StatelessWidget {
  final Doc doc;
  final double fontSize;
  const _HorizontalReader({required this.doc, required this.fontSize});

  @override
  Widget build(BuildContext context) {
    final base = TextStyle(
        fontSize: fontSize, height: 1.9, color: Sumi.ink, fontFamily: 'IPAexMincho');
    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      itemCount: doc.paras.length + (doc.colophon.isEmpty ? 0 : 1),
      itemBuilder: (context, i) {
        if (i == doc.paras.length) {
          return Padding(
            padding: const EdgeInsets.only(top: 28),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Divider(),
                Text(doc.colophon,
                    style: TextStyle(
                        fontSize: fontSize * 0.72,
                        height: 1.8,
                        color: Sumi.muted)),
              ],
            ),
          );
        }
        final p = doc.paras[i];
        if (p.image != null) {
          final img = p.image!;
          return Padding(
            padding: const EdgeInsets.symmetric(vertical: 10),
            child: Column(children: [
              Image.network(img.src,
                  width: img.w?.toDouble(),
                  errorBuilder: (c, e, s) => Text('〔挿絵: ${img.cap}〕',
                      style: const TextStyle(color: Sumi.muted))),
              if (img.cap.isNotEmpty)
                Text(img.cap,
                    style: TextStyle(
                        fontSize: fontSize * 0.7, color: Sumi.muted)),
            ]),
          );
        }
        final style = p.h != 0
            ? base.copyWith(
                fontSize: fontSize * (p.h == 2 ? 1.35 : (p.h == 3 ? 1.2 : 1.1)),
                color: Sumi.shu,
                height: 2.2)
            : base;
        final text = Text.rich(TextSpan(
            style: style, children: paragraphSpans(p, style)));
        return Padding(
          padding: EdgeInsets.only(
              left: p.indent * fontSize,
              top: p.h != 0 ? fontSize : 0,
              bottom: 4),
          child: p.align == 'right'
              ? Align(
                  alignment: Alignment.centerRight,
                  child: Padding(
                      padding:
                          EdgeInsets.only(right: p.alignOffset * fontSize),
                      child: text))
              : text,
        );
      },
    );
  }
}
