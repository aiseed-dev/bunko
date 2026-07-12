/// 読書画面 —— doc列のUnicodeデータを描くだけ（外字も実文字・画像も注記も無し）。
///
/// 機能: 横書き（ルビ上付き・ドラッグ選択コピー）／縦書き（自前レイアウト）、
/// 目次（公式XHTMLの目次パネルと同じ見出し階層リスト・現在位置しおり）、
/// 音声読み上げ（ルビ＝読みデータで誤読しない・段落ハイライト同期・自動追従）、
/// 全文コピー、文字サイズ。未取得の本文はミラーから取得しdocへ保存。
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:scrollable_positioned_list/scrollable_positioned_list.dart';

import '../data/db.dart';
import '../data/fetch.dart';
import '../data/models.dart';
import '../data/toc.dart';
import '../theme.dart';
import 'audiobook_controller.dart';
import 'card_view.dart';
import 'ruby_text.dart';
import 'tts_controller.dart';
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
  late Future<Doc> _docFuture;
  Doc? _doc;
  double _fontSize = 19;
  bool _vertical = false;
  bool _showCard = true; // デスクトップ: 左に図書カード

  // 横書き: 目次ジャンプ・現在位置
  final _itemScroll = ItemScrollController();
  final _itemPositions = ItemPositionsListener.create();

  // 縦書き: ジャンプ・現在位置
  final _vScroll = ScrollController();
  VerticalLayout? _vLayout;

  // 読み上げ（端末TTS）と朗読パック（事前合成audiobook）
  final ReaderTts? _tts = ttsSupported ? ReaderTts() : null;
  final ReaderAudiobook _book = ReaderAudiobook();
  bool _bookReady = false; // パックが見つかった
  bool _bookOpen = false; // 再生バーを開いている
  final ValueNotifier<int?> _hl = ValueNotifier(null); // 段落ハイライト（TTS/朗読の合流）

  @override
  void initState() {
    super.initState();
    _docFuture = _load();
    _tts?.current.addListener(_followTts);
    _book.current.addListener(_followBook);
    _book.load(widget.work.workId).then((ok) {
      if (ok && mounted) setState(() => _bookReady = true);
    });
  }

  @override
  void dispose() {
    _tts?.current.removeListener(_followTts);
    _tts?.dispose();
    _book.current.removeListener(_followBook);
    _book.dispose();
    _hl.dispose();
    _vScroll.dispose();
    super.dispose();
  }

  Future<Doc> _load() async {
    final cached = widget.db.loadDoc(widget.work.workId);
    final doc = cached ?? await widget.fetcher.fetchDoc(widget.work);
    _doc = doc;
    if (mounted) setState(() {}); // 目次・読み上げボタンを有効化
    return doc;
  }

  // ── 現在位置（目次マーカー・読み上げ開始点） ─────────────────
  int _currentParaIndex() {
    if (_vertical) {
      final layout = _vLayout;
      if (layout == null) return 0;
      final col = (_vScroll.hasClients ? _vScroll.offset : 0) / layout.colW;
      for (var i = 0; i < layout.paraCols.length; i++) {
        if (layout.paraCols[i].$2 > col) return i;
      }
      return layout.paraCols.isEmpty ? 0 : layout.paraCols.length - 1;
    }
    final positions = _itemPositions.itemPositions.value;
    if (positions.isEmpty) return 0;
    return positions
        .where((p) => p.itemTrailingEdge > 0)
        .map((p) => p.index)
        .fold<int?>(null, (m, i) => m == null || i < m ? i : m) ??
        0;
  }

  void _jumpTo(int paraIndex) {
    final doc = _doc;
    if (doc == null) return;
    if (_vertical) {
      final layout = _vLayout;
      if (layout == null || !_vScroll.hasClients) return;
      final offset = paraIndex >= layout.paraCols.length
          ? _vScroll.position.maxScrollExtent
          : layout.paraCols[paraIndex].$1 * layout.colW;
      _vScroll.animateTo(
          offset.clamp(0.0, _vScroll.position.maxScrollExtent),
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut);
    } else if (_itemScroll.isAttached) {
      _itemScroll.scrollTo(
          index: paraIndex.clamp(0, doc.paras.length),
          duration: const Duration(milliseconds: 300),
          alignment: 0.08);
    }
  }

  void _followTts() {
    final i = _tts?.current.value;
    _hl.value = i ?? _book.current.value;
    if (i != null && mounted) _jumpTo(i);
    if (mounted) setState(() {}); // 縦書きハイライト・再生アイコン更新
  }

  void _followBook() {
    final i = _book.current.value;
    _hl.value = _tts?.current.value ?? i;
    if (i != null && mounted) _jumpTo(i);
    if (mounted) setState(() {});
  }

  // ── 目次シート（公式の目次パネル準拠: 見出し階層のみ＋現在位置しおり） ──
  void _showToc(Doc doc) {
    final entries = buildToc(doc);
    final current = _currentParaIndex();
    showModalBottomSheet(
      context: context,
      backgroundColor: Sumi.paperHi,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(14))),
      builder: (sheet) {
        if (entries.isEmpty) {
          return const Padding(
            padding: EdgeInsets.all(28),
            child: Text('この作品に目次（見出し）はありません',
                style: TextStyle(color: Sumi.muted)),
          );
        }
        var activeIdx = 0;
        for (var k = 0; k < entries.length; k++) {
          if (entries[k].paraIndex <= current) activeIdx = k;
        }
        return SafeArea(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 14, 20, 6),
              child: Row(children: [
                const Text('目次',
                    style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: Sumi.shu,
                        letterSpacing: 4)),
                const Spacer(),
                Text(doc.title,
                    style: const TextStyle(fontSize: 12, color: Sumi.muted)),
              ]),
            ),
            const Divider(height: 1),
            Flexible(
              child: ListView.builder(
                shrinkWrap: true,
                itemCount: entries.length,
                itemBuilder: (context, k) {
                  final e = entries[k];
                  final active = k == activeIdx;
                  final indent = switch (e.level) {
                    3 => 18.0,
                    4 => 36.0,
                    _ => 0.0,
                  };
                  return InkWell(
                    onTap: () {
                      Navigator.of(sheet).pop();
                      _jumpTo(e.paraIndex);
                    },
                    child: Padding(
                      padding: EdgeInsets.only(
                          left: 20 + indent, right: 20, top: 9, bottom: 9),
                      child: Row(children: [
                        Container(
                            width: 3,
                            height: 18,
                            margin: const EdgeInsets.only(right: 10),
                            color: active ? Sumi.shu : Colors.transparent),
                        Expanded(
                          child: Text(e.label,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(
                                fontSize: e.level == 2 ? 15 : 13.5,
                                fontWeight: e.level == 2
                                    ? FontWeight.w600
                                    : FontWeight.w400,
                                color: active ? Sumi.shu : Sumi.ink,
                              )),
                        ),
                      ]),
                    ),
                  );
                },
              ),
            ),
          ]),
        );
      },
    );
  }

  Future<void> _copyAll(Doc doc) async {
    final text = doc.paras.map((p) => p.plain).join('\n');
    await Clipboard.setData(ClipboardData(text: text));
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('全文をコピーしました（${text.length}字・ルビなし本文）')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final playing = _tts?.current.value != null;
    return Scaffold(
      appBar: AppBar(
        title: Text('${widget.work.title} ／ ${widget.work.author}',
            style: const TextStyle(fontSize: 15)),
        actions: [
          if (MediaQuery.sizeOf(context).width >= 1100)
            IconButton(
              tooltip: _showCard ? '図書カードを隠す' : '図書カードを表示',
              icon: Icon(Icons.badge_outlined,
                  color: _showCard ? Sumi.shu : null),
              onPressed: () => setState(() => _showCard = !_showCard),
            ),
          IconButton(
            tooltip: '目次',
            icon: const Icon(Icons.toc),
            onPressed: _doc == null ? null : () => _showToc(_doc!),
          ),
          if (_bookReady)
            IconButton(
              tooltip: _bookOpen ? '朗読を閉じる' : '朗読パックを聴く（事前合成の音声）',
              icon: Icon(_bookOpen ? Icons.headset_off : Icons.headset,
                  color: _bookOpen ? Sumi.shu : null),
              onPressed: () async {
                if (_bookOpen) {
                  await _book.stop();
                  setState(() => _bookOpen = false);
                } else {
                  _tts?.stop();
                  setState(() => _bookOpen = true);
                  await _book.toggle();
                }
              },
            ),
          if (_tts != null)
            IconButton(
              tooltip: playing ? '読み上げを止める' : 'ここから読み上げ（ルビの読みで朗読）',
              icon: Icon(playing ? Icons.stop_circle : Icons.play_circle,
                  color: playing ? Sumi.shu : null),
              onPressed: _doc == null
                  ? null
                  : () => playing
                      ? _tts.stop()
                      : _tts.playFrom(_doc!.paras, _currentParaIndex()),
            ),
          IconButton(
            tooltip: _vertical ? '横書きにする' : '縦書きにする',
            icon: Icon(_vertical
                ? Icons.text_rotation_none
                : Icons.text_rotate_vertical),
            onPressed: () => setState(() => _vertical = !_vertical),
          ),
          PopupMenuButton<String>(
            tooltip: 'その他',
            onSelected: (v) {
              switch (v) {
                case 'copy':
                  if (_doc != null) _copyAll(_doc!);
                case 'larger':
                  setState(() => _fontSize = (_fontSize + 2).clamp(12, 34));
                case 'smaller':
                  setState(() => _fontSize = (_fontSize - 2).clamp(12, 34));
              }
            },
            itemBuilder: (context) => const [
              PopupMenuItem(value: 'copy', child: Text('全文コピー（ルビなし）')),
              PopupMenuItem(value: 'larger', child: Text('文字を大きく')),
              PopupMenuItem(value: 'smaller', child: Text('文字を小さく')),
            ],
          ),
        ],
      ),
      bottomNavigationBar: (_bookReady && _bookOpen)
          ? _AudiobookBar(book: _book, onClose: () async {
              await _book.stop();
              setState(() => _bookOpen = false);
            })
          : null,
      body: LayoutBuilder(builder: (context, box) {
        final reading = _buildReading();
        if (box.maxWidth < 1100 || !_showCard) return reading;
        return Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          SizedBox(
            width: 300,
            child: Container(
              color: Sumi.paperHi,
              child: CardView(
                  work: widget.work,
                  db: widget.db,
                  fetcher: widget.fetcher,
                  compact: true,
                  showHeader: true),
            ),
          ),
          const VerticalDivider(width: 1, color: Sumi.rule),
          Expanded(child: reading),
        ]);
      }),
    );
  }

  Widget _buildReading() {
    return FutureBuilder<Doc>(
        future: _docFuture,
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
          if (_vertical) {
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: VerticalReader(
                doc: doc,
                fontSize: _fontSize,
                controller: _vScroll,
                highlightPara: _hl.value,
                onLayout: (l) => _vLayout = l,
              ),
            );
          }
          // 横書き: SelectionArea でドラッグ選択コピー（ルビは選択対象外）
          return SelectionArea(
            child: _HorizontalReader(
              doc: doc,
              fontSize: _fontSize,
              itemScroll: _itemScroll,
              itemPositions: _itemPositions,
              ttsCurrent: _hl,
            ),
          );
        },
      );
  }
}

class _HorizontalReader extends StatelessWidget {
  final Doc doc;
  final double fontSize;
  final ItemScrollController itemScroll;
  final ItemPositionsListener itemPositions;
  final ValueNotifier<int?>? ttsCurrent;
  const _HorizontalReader(
      {required this.doc,
      required this.fontSize,
      required this.itemScroll,
      required this.itemPositions,
      this.ttsCurrent});

  @override
  Widget build(BuildContext context) {
    final base = TextStyle(
        fontSize: fontSize,
        height: 1.9,
        color: Sumi.ink,
        fontFamily: 'IPAexMincho');
    final itemCount = doc.paras.length + (doc.colophon.isEmpty ? 0 : 1);
    return ScrollablePositionedList.builder(
      itemScrollController: itemScroll,
      itemPositionsListener: itemPositions,
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      itemCount: itemCount,
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
        final child = _paragraph(doc.paras[i], base);
        final notifier = ttsCurrent;
        if (notifier == null) return child;
        // 読み上げ中の段落を淡い朱でハイライト
        return ValueListenableBuilder<int?>(
          valueListenable: notifier,
          builder: (context, cur, _) => DecoratedBox(
            decoration: BoxDecoration(
              color: cur == i
                  ? Sumi.shu.withValues(alpha: 0.08)
                  : Colors.transparent,
              borderRadius: BorderRadius.circular(4),
            ),
            child: child,
          ),
        );
      },
    );
  }

  Widget _paragraph(Para p, TextStyle base) {
    if (p.pb != null) {
      // 改丁・改ページ・改段: 読書UIでは控えめな区切り
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 26),
        child: Row(children: [
          const Expanded(child: Divider(color: Sumi.rule)),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14),
            child: Text('※',
                style: TextStyle(
                    fontSize: base.fontSize! * 0.7, color: Sumi.muted)),
          ),
          const Expanded(child: Divider(color: Sumi.rule)),
        ]),
      );
    }
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
                    fontSize: base.fontSize! * 0.7, color: Sumi.muted)),
        ]),
      );
    }
    final style = p.h != 0
        ? base.copyWith(
            fontSize:
                base.fontSize! * (p.h == 2 ? 1.35 : (p.h == 3 ? 1.2 : 1.1)),
            color: Sumi.shu,
            height: 2.2)
        : base;
    final text =
        Text.rich(TextSpan(style: style, children: paragraphSpans(p, style)));
    return Padding(
      padding: EdgeInsets.only(
          left: p.indent * base.fontSize!,
          top: p.h != 0 ? base.fontSize! : 0,
          bottom: 4),
      child: p.align == 'right'
          ? Align(
              alignment: Alignment.centerRight,
              child: Padding(
                  padding:
                      EdgeInsets.only(right: p.alignOffset * base.fontSize!),
                  child: text))
          : text,
    );
  }
}

/// 朗読パックの再生バー（下端固定）: 再生/停止・シーク・残り時間。
class _AudiobookBar extends StatelessWidget {
  final ReaderAudiobook book;
  final VoidCallback onClose;
  const _AudiobookBar({required this.book, required this.onClose});

  String _fmt(double sec) {
    final s = sec.round();
    return '${s ~/ 60}:${(s % 60).toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    final total = book.book?.total ?? 0;
    return Material(
      color: Sumi.paperHi,
      child: SafeArea(
        child: SizedBox(
          height: 56,
          child: StreamBuilder<Duration>(
            stream: book.positionStream,
            builder: (context, snap) {
              final pos = (snap.data ?? Duration.zero).inMilliseconds / 1000.0;
              return Row(children: [
                const SizedBox(width: 4),
                StreamBuilder(
                  stream: book.stateStream,
                  builder: (context, _) => IconButton(
                    icon: Icon(
                        book.playing
                            ? Icons.pause_circle_filled
                            : Icons.play_circle_fill,
                        color: Sumi.shu,
                        size: 34),
                    onPressed: () => book.toggle(),
                  ),
                ),
                Text(_fmt(pos),
                    style: const TextStyle(fontSize: 11, color: Sumi.muted)),
                Expanded(
                  child: Slider(
                    value: pos.clamp(0, total),
                    max: total <= 0 ? 1 : total,
                    activeColor: Sumi.shu,
                    inactiveColor: Sumi.rule,
                    onChanged: (v) => book.seek(
                        Duration(microseconds: (v * 1e6).round())),
                  ),
                ),
                Text(_fmt(total),
                    style: const TextStyle(fontSize: 11, color: Sumi.muted)),
                IconButton(
                    icon: const Icon(Icons.close, size: 18, color: Sumi.muted),
                    tooltip: '朗読を閉じる',
                    onPressed: onClose),
                const SizedBox(width: 4),
              ]);
            },
          ),
        ),
      ),
    );
  }
}
