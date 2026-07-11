/// 縦書きレンダラ —— Flutter に writing-mode は無いので自前レイアウト。
///
/// 文字を上→下に積み、行（列）を右→左へ送る。ルビ・傍点は行間（親文字の右）に。
/// 長音・括弧類は90°回転、句読点は升目の右上へ寄せる（フォント非依存の幾何対応、
/// flutter_svg_cjk_friendly の縦書き手法と同じ考え方）。
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../data/models.dart';
import '../theme.dart';

const _rotate = 'ー－‐〜～…‥—―=＝（）()「」『』［］[]｛｝{}〈〉《》【】';
const _kutou = '、。，．';

class Glyph {
  final String ch;
  final double x, y, size;
  final Color color;
  final bool rotate;
  final bool shiftTopRight;
  const Glyph(this.ch, this.x, this.y, this.size, this.color,
      {this.rotate = false, this.shiftTopRight = false});
}

/// 段落列 → グリフ配置（列は左端x=0基準で計算し、描画時に右起点へ反転）
class VerticalLayout {
  final List<Glyph> glyphs = [];
  /// 段落ごとの (開始列, 終了列exclusive) —— 目次ジャンプ・読み上げハイライト用
  final List<(int, int)> paraCols = [];
  late final double colW;
  late final double width;
  final double height;
  final double fontSize;

  VerticalLayout(List<Para> paras,
      {required this.height, required this.fontSize}) {
    colW = fontSize * 1.9; // 行送り（ルビの溝を含む）
    final step = fontSize * 1.18; // 字送り
    final padV = fontSize;
    final usable = height - padV * 2;

    var col = 0;
    var y = padV;

    void newColumn([int extra = 1]) {
      col += extra;
      y = padV;
    }

    void putRun(String base, String? ruby, Color color, double size,
        {bool heading = false}) {
      final chars = base.split('');
      final startY = y;
      for (final ch in chars) {
        if (y + step > padV + usable) newColumn();
        final x = col * colW;
        if (_kutou.contains(ch)) {
          glyphs.add(Glyph(ch, x, y, size, color, shiftTopRight: true));
        } else if (_rotate.contains(ch)) {
          glyphs.add(Glyph(ch, x, y, size, color, rotate: true));
        } else {
          glyphs.add(Glyph(ch, x, y, size, color));
        }
        y += step * (heading ? 1.08 : 1.0);
      }
      if (ruby != null && chars.isNotEmpty) {
        final rChars = ruby.split('');
        final runLen = y - startY;
        final rStep = runLen / rChars.length;
        var ry = startY;
        for (final rc in rChars) {
          glyphs.add(Glyph(
              rc, col * colW + fontSize * 1.06, ry, size * 0.5, Sumi.muted));
          ry += rStep;
        }
      }
    }

    for (final p in paras) {
      final paraStartCol = col;
      if (p.image != null) {
        paraCols.add((col, col));
        continue; // v1: 縦書きでは挿絵スキップ
      }
      final heading = p.h != 0;
      final color = heading ? Sumi.shu : Sumi.ink;
      final size = heading ? fontSize * 1.15 : fontSize;
      if (heading) newColumn(2); // 見出し前は一行空け
      y += p.indent * step; // 字下げ＝列頭の下げ

      // 傍点対象の文字集合（親文字の右に圏点）
      final boutenTargets = <String>{
        for (final d in p.decos)
          if (d.tag == 'em' && d.cls.contains('dot') ||
              d.cls.contains('circle') ||
              d.cls == 'saltire' ||
              d.cls == 'bullseye' ||
              d.cls == 'fisheye')
            d.t
      };

      for (final s in p.segs) {
        if (s.r != null) {
          putRun(s.t, s.r, color, size, heading: heading);
        } else {
          var text = s.t;
          // 傍点: 対象部分だけ「・」ルビとして出す
          var done = false;
          for (final t in boutenTargets) {
            final i = text.indexOf(t);
            if (i >= 0) {
              if (i > 0) putRun(text.substring(0, i), null, color, size);
              putRun(t, '・' * t.length, color, size);
              if (i + t.length < text.length) {
                putRun(text.substring(i + t.length), null, color, size);
              }
              done = true;
              break;
            }
          }
          if (!done) putRun(text, null, color, size, heading: heading);
        }
      }
      newColumn(); // 段落＝改行（次の列へ）
      paraCols.add((paraStartCol, col));
      if (heading) newColumn();
    }
    width = (col + 1) * colW + fontSize * 2;
  }
}

class VerticalReader extends StatelessWidget {
  final Doc doc;
  final double fontSize;
  final ScrollController? controller;
  final int? highlightPara; // 読み上げ中の段落
  final void Function(VerticalLayout layout)? onLayout; // 目次ジャンプ用に測定結果を返す
  const VerticalReader(
      {super.key,
      required this.doc,
      required this.fontSize,
      this.controller,
      this.highlightPara,
      this.onLayout});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, constraints) {
      final layout = VerticalLayout(doc.paras,
          height: constraints.maxHeight, fontSize: fontSize);
      onLayout?.call(layout);
      return SingleChildScrollView(
        controller: controller,
        scrollDirection: Axis.horizontal,
        reverse: true, // 冒頭（右端）から
        child: CustomPaint(
          size: Size(layout.width, constraints.maxHeight),
          painter: _VerticalPainter(layout, highlightPara),
        ),
      );
    });
  }
}

class _VerticalPainter extends CustomPainter {
  final VerticalLayout layout;
  final int? highlightPara;
  _VerticalPainter(this.layout, [this.highlightPara]);

  final _cache = <String, TextPainter>{};

  TextPainter _tp(String ch, double size, Color color) {
    final key = '$ch|$size|${color.toARGB32()}';
    return _cache.putIfAbsent(key, () {
      final tp = TextPainter(
        text: TextSpan(
            text: ch,
            style: TextStyle(
                fontFamily: 'IPAexMincho',
                fontSize: size,
                color: color,
                height: 1.0)),
        textDirection: TextDirection.ltr,
      )..layout();
      return tp;
    });
  }

  @override
  void paint(Canvas canvas, Size size) {
    // 読み上げ中の段落を淡い朱でハイライト（列範囲を塗る）
    final hp = highlightPara;
    if (hp != null && hp < layout.paraCols.length) {
      final (c0, c1) = layout.paraCols[hp];
      if (c1 > c0) {
        final xRight = size.width - c0 * layout.colW;
        final xLeft = size.width - c1 * layout.colW;
        canvas.drawRect(
          Rect.fromLTRB(xLeft - layout.fontSize * 0.4, 0,
              xRight + layout.fontSize * 0.2, size.height),
          Paint()..color = Sumi.shu.withValues(alpha: 0.08),
        );
      }
    }
    for (final g in layout.glyphs) {
      // 列は右→左: 論理x を右起点に反転
      final x = size.width - g.x - g.size * 1.6;
      final tp = _tp(g.ch, g.size, g.color);
      if (g.rotate) {
        canvas.save();
        canvas.translate(x + g.size / 2, g.y + g.size / 2);
        canvas.rotate(math.pi / 2);
        tp.paint(canvas, Offset(-tp.width / 2, -tp.height / 2));
        canvas.restore();
      } else if (g.shiftTopRight) {
        tp.paint(canvas, Offset(x + g.size * 0.55, g.y - g.size * 0.28));
      } else {
        tp.paint(canvas, Offset(x + (g.size - tp.width) / 2, g.y));
      }
    }
  }

  @override
  bool shouldRepaint(_VerticalPainter old) =>
      old.layout != layout || old.highlightPara != highlightPara;
}
