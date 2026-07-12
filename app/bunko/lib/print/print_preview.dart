/// 印刷プレビュー —— buildPrintPages のSVG頁をそのまま表示し、
/// 同じSVGを pdf パッケージでA4 PDFに組んで印刷ダイアログへ渡す。
/// プレビュー描画は flutter_svg_cjk_friendly（自作OSS）でCJK豆腐を回避。
library;

import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show Uint8List;
import 'package:flutter/services.dart' show rootBundle;
import 'package:flutter_svg/flutter_svg.dart';
import 'package:flutter_svg_cjk_friendly/flutter_svg_cjk_friendly.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';

import '../data/models.dart';
import '../theme.dart';
import 'print_pages.dart';

class PrintPreviewPage extends StatefulWidget {
  final Doc doc;
  const PrintPreviewPage({super.key, required this.doc});

  @override
  State<PrintPreviewPage> createState() => _PrintPreviewPageState();
}

class _PrintPreviewPageState extends State<PrintPreviewPage> {
  late final List<String> _pages = buildPrintPages(widget.doc);
  final _pageCtrl = PageController();
  int _current = 0;
  bool _printing = false;

  Future<Uint8List> _buildPdf(PdfPageFormat format) async {
    final data = await rootBundle.load('assets/fonts/ipaexm.ttf');
    final ttf = pw.Font.ttf(data);
    final doc = pw.Document(title: widget.doc.title);
    for (final page in _pages) {
      doc.addPage(pw.Page(
        pageFormat: PdfPageFormat.a4,
        margin: pw.EdgeInsets.zero,
        build: (ctx) => pw.SvgImage(
            svg: page, customFontLookup: (family, style, weight) => ttf),
      ));
    }
    return doc.save();
  }

  Future<void> _print() async {
    setState(() => _printing = true);
    try {
      await Printing.layoutPdf(
          name: widget.doc.title, onLayout: _buildPdf);
    } finally {
      if (mounted) setState(() => _printing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Sumi.rule,
      appBar: AppBar(
        title: Text('印刷プレビュー ── ${widget.doc.title}（A4縦書き・${_pages.length}頁）',
            style: const TextStyle(fontSize: 14)),
        actions: [
          if (_printing)
            const Padding(
              padding: EdgeInsets.all(14),
              child: SizedBox(
                  width: 18, height: 18,
                  child: CircularProgressIndicator(
                      strokeWidth: 2, color: Sumi.shu)),
            )
          else
            IconButton(
                tooltip: '印刷（またはPDF保存）',
                icon: const Icon(Icons.print),
                onPressed: _print),
        ],
      ),
      body: Column(children: [
        Expanded(
          child: PageView.builder(
            controller: _pageCtrl,
            onPageChanged: (i) => setState(() => _current = i),
            itemCount: _pages.length,
            itemBuilder: (context, i) => Center(
              child: AspectRatio(
                aspectRatio: pageW / pageH,
                child: Container(
                  margin: const EdgeInsets.all(12),
                  decoration: BoxDecoration(color: Colors.white, boxShadow: [
                    BoxShadow(
                        color: Colors.black.withValues(alpha: .18),
                        blurRadius: 10)
                  ]),
                  child: SvgPicture.string(
                      cjkFriendlySvg(_pages[i],
                          preferred: const ['IPAexMincho']),
                      fit: BoxFit.contain),
                ),
              ),
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.only(bottom: 10, top: 2),
          child: Text('${_current + 1} / ${_pages.length}',
              style: const TextStyle(fontSize: 12, color: Sumi.inkSoft)),
        ),
      ]),
    );
  }
}
