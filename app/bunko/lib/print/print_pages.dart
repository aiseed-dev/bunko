/// 印刷ページ生成 —— 画面の縦書きエンジン（VerticalLayout）の文字座標を
/// そのまま A4 の SVG 頁に写す。プレビュー（flutter_svg_cjk_friendly）と
/// PDF（pdf パッケージ・フォント埋め込み）が**同じSVG**を使うので、
/// 見たままが刷り上がる。用紙は A4 固定・右起こし縦組み・ノンブル付き。
library;

import 'package:flutter/material.dart' show Color;

import '../data/models.dart';
import '../theme.dart';
import '../ui/vertical_reader.dart';

const double pageW = 595, pageH = 842; // A4 (pt)
const double _marginX = 46, _marginY = 52;

String _esc(String s) => s
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');

String _hex(Color c) =>
    '#${(c.toARGB32() & 0xFFFFFF).toRadixString(16).padLeft(6, '0')}';

/// Doc → A4縦書きSVG頁の列。題名・著者を冒頭に添える。
List<String> buildPrintPages(Doc doc, {double fontSize = 14}) {
  final paras = [
    Para(segs: [Seg(doc.title)], h: 2),
    Para(segs: [Seg(doc.author)]),
    ...doc.paras,
  ];
  final usableH = pageH - _marginY * 2;
  final usableW = pageW - _marginX * 2;
  final layout = VerticalLayout(paras, height: usableH, fontSize: fontSize);
  final pageCols = (usableW / layout.colW).floor().clamp(1, 999);
  final pagesColsW = pageCols * layout.colW;

  var totalCols = 1;
  for (final g in layout.glyphs) {
    final col = (g.x / layout.colW).floor();
    if (col + 1 > totalCols) totalCols = col + 1;
  }
  final pageCount = (totalCols / pageCols).ceil();

  final bufs = List.generate(pageCount, (i) {
    final b = StringBuffer(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 $pageW $pageH" '
        'width="$pageW" height="$pageH">');
    b.write('<rect width="$pageW" height="$pageH" fill="#ffffff"/>');
    return b;
  });

  for (final g in layout.glyphs) {
    // colW は浮動小数（fontSize*1.9）なので、丸め誤差に強い round を使う
    // （ルビは列基準 +1.06em に置かれるため round でも親列に正しく落ちる…
    //  とはいえ +0.5列を超えないよう、ルビぶんを引いてから丸める）
    final col = ((g.x - (g.size < layout.fontSize * 0.9
                ? layout.fontSize * 1.06
                : 0)) /
            layout.colW)
        .round();
    final p = col ~/ pageCols;
    // 列は右→左。列の基準位置（親文字サイズ基準）を先に決め、
    // ルビ（半サイズ）は親列の右に添える —— 反転式に小サイズを
    // 通すと親文字に重なるため。
    final colBase = _marginX +
        pagesColsW -
        (col * layout.colW - p * pagesColsW) -
        layout.fontSize * 1.6;
    final isRuby = g.size < layout.fontSize * 0.9;
    final x = isRuby ? colBase + layout.fontSize * 1.06 : colBase;
    final yTop = _marginY + (g.y - layout.fontSize);
    final color = _hex(g.color);
    final b = bufs[p];
    final ch = _esc(g.ch);
    if (g.rotate) {
      final cx = x + g.size / 2, cy = yTop + g.size / 2;
      b.write('<g transform="translate($cx,$cy) rotate(90)">'
          '<text x="0" y="0" text-anchor="middle" dominant-baseline="central" '
          'font-family="IPAexMincho" font-size="${g.size}" fill="$color">'
          '$ch</text></g>');
    } else if (g.shiftTopRight) {
      b.write('<text x="${x + g.size * 0.55}" '
          'y="${yTop - g.size * 0.28 + g.size * 0.88}" '
          'font-family="IPAexMincho" font-size="${g.size}" fill="$color">'
          '$ch</text>');
    } else {
      b.write('<text x="${x + g.size / 2}" y="${yTop + g.size * 0.88}" '
          'text-anchor="middle" '
          'font-family="IPAexMincho" font-size="${g.size}" fill="$color">'
          '$ch</text>');
    }
  }

  final muted = _hex(Sumi.muted);
  for (var i = 0; i < pageCount; i++) {
    bufs[i].write('<text x="${pageW / 2}" y="${pageH - 24}" '
        'text-anchor="middle" font-family="IPAexMincho" font-size="9" '
        'fill="$muted">${i + 1} / $pageCount</text>');
    bufs[i].write('</svg>');
  }
  return [for (final b in bufs) b.toString()];
}
