/// ルビ・装飾つき段落の横書き描画。
///
/// ルビは WidgetSpan（ルビ上・親文字下の小コラム）で行折返しに自然に混ざる。
/// 傍点は印刷の慣習どおり「ルビ位置に圏点」を置く（sesame_dot → ﹅ など）。
library;

import 'package:flutter/material.dart';

import '../data/models.dart';
import '../theme.dart';

/// 傍点類 → 圏点1文字（親文字1字ごとに上に置く）
const _boutenChar = {
  'sesame_dot': '﹅',
  'white_sesame_dot': '﹆',
  'black_circle': '●',
  'white_circle': '○',
  'black_up-pointing_triangle': '▲',
  'white_up-pointing_triangle': '△',
  'bullseye': '◎',
  'fisheye': '◉',
  'saltire': '×',
};

TextStyle _decoStyle(String cls, TextStyle base) {
  if (cls == 'futoji') return base.copyWith(fontWeight: FontWeight.bold);
  if (cls == 'shatai') return base.copyWith(fontStyle: FontStyle.italic);
  if (cls.startsWith('underline_') || cls.startsWith('overline_')) {
    return base.copyWith(
      decoration: cls.startsWith('under')
          ? TextDecoration.underline
          : TextDecoration.overline,
      decorationStyle: switch (cls.split('_').last) {
        'double' => TextDecorationStyle.double,
        'dotted' => TextDecorationStyle.dotted,
        'dashed' => TextDecorationStyle.dashed,
        'wave' => TextDecorationStyle.wavy,
        _ => TextDecorationStyle.solid,
      },
    );
  }
  return base;
}

class RubyUnit extends StatelessWidget {
  final String base;
  final String ruby;
  final TextStyle style;
  const RubyUnit(
      {super.key, required this.base, required this.ruby, required this.style});

  @override
  Widget build(BuildContext context) {
    final size = style.fontSize ?? 18;
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // ルビは表示のみ（コピー選択から除外 → コピー結果が本文だけになる）
        SelectionContainer.disabled(
          child: Text(ruby,
              style: style.copyWith(
                  fontSize: size * 0.5, color: Sumi.muted, height: 1.0)),
        ),
        Text(base, style: style.copyWith(height: 1.1)),
      ],
    );
  }
}

/// 段落 → InlineSpan列（ルビ・傍点・太字等を適用）
List<InlineSpan> paragraphSpans(Para p, TextStyle style) {
  // 装飾（傍点→圏点ルビ / 太字等→スタイル）を適用しながらセグメントを展開する。
  // 装飾対象は plain 上の文字列。ルビの無いセグメント内でのみマッチさせる（v1）。
  final decos = List<Deco>.of(p.decos);
  final spans = <InlineSpan>[];

  void addPlain(String text) {
    var rest = text;
    while (rest.isNotEmpty && decos.isNotEmpty) {
      Deco? hit;
      var hitAt = -1;
      for (final d in decos) {
        final i = rest.indexOf(d.t);
        if (i >= 0 && (hitAt < 0 || i < hitAt)) {
          hit = d;
          hitAt = i;
        }
      }
      if (hit == null) break;
      if (hitAt > 0) spans.add(TextSpan(text: rest.substring(0, hitAt)));
      final bouten = _boutenChar[hit.cls.replaceAll('_after', '')];
      if (bouten != null) {
        // 傍点: 1文字ずつ圏点をルビ位置に
        for (final ch in hit.t.split('')) {
          spans.add(WidgetSpan(
            alignment: PlaceholderAlignment.bottom,
            child: RubyUnit(base: ch, ruby: bouten, style: style),
          ));
        }
      } else {
        spans.add(TextSpan(text: hit.t, style: _decoStyle(hit.cls, style)));
      }
      rest = rest.substring(hitAt + hit.t.length);
      decos.remove(hit);
    }
    if (rest.isNotEmpty) spans.add(TextSpan(text: rest));
  }

  for (final s in p.segs) {
    if (s.r != null) {
      spans.add(WidgetSpan(
        alignment: PlaceholderAlignment.bottom,
        child: RubyUnit(base: s.t, ruby: s.r!, style: style),
      ));
    } else {
      addPlain(s.t);
    }
  }
  return spans;
}
