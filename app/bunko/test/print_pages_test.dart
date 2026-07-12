/// 印刷ページ生成のテスト: A4 SVG頁への割付と、pdfパッケージでのPDF化。
@TestOn('vm')
library;

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;

import 'package:bunko/data/models.dart';
import 'package:bunko/print/print_pages.dart';

Doc _doc(int paras) => Doc(title: '走れメロス', author: '太宰治', paras: [
      for (var i = 0; i < paras; i++)
        Para(segs: [
          Seg('第$i段落。'),
          Seg('邪智暴虐', 'じゃちぼうぎゃく'),
          Seg('の王を（除く）ー。'),
        ]),
    ]);

void main() {
  test('A4頁に割り付き、全頁が整形式SVGでノンブルを持つ', () {
    final pages = buildPrintPages(_doc(40));
    expect(pages.length, greaterThan(1));
    for (var i = 0; i < pages.length; i++) {
      expect(pages[i], startsWith('<svg '));
      expect(pages[i], endsWith('</svg>'));
      expect(pages[i], contains('${i + 1} / ${pages.length}'));
      expect(pages[i], contains('IPAexMincho'));
    }
    // ルビ・回転括弧・長音の変換も落ちない
    expect(pages[0], contains('じ'));
    expect(pages[0], contains('rotate(90)'));
  });

  test('SVG頁を pdf パッケージで A4 PDF に組める（フォント埋め込み）', () async {
    final pages = buildPrintPages(_doc(12));
    final ttf = pw.Font.ttf(
        File('assets/fonts/ipaexm.ttf').readAsBytesSync().buffer.asByteData());
    final doc = pw.Document();
    for (final page in pages) {
      doc.addPage(pw.Page(
        pageFormat: PdfPageFormat.a4,
        margin: pw.EdgeInsets.zero,
        build: (ctx) => pw.SvgImage(
            svg: page, customFontLookup: (f, s, w) => ttf),
      ));
    }
    final bytes = await doc.save();
    File('build/print_pages.pdf').writeAsBytesSync(bytes);
    expect(bytes.length, greaterThan(10000));
  });
}
