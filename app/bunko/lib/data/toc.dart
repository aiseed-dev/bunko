/// 目次（しおり）の生成 —— パース済み見出しから作る。工夫は3つ:
///
/// 1. 見出し階層（大/中/小）と**各章の分量バー**（章の字数比）を持つ
/// 2. 見出しの無い作品には**進捗ジャンプ**（10%刻み・冒頭抜粋つき）を自動生成
/// 3. 末尾に「底本」項目（colophonがあれば）
library;

import 'models.dart';

enum TocKind { heading, percent, colophon }

class TocEntry {
  final TocKind kind;
  final int paraIndex; // ジャンプ先の段落index（colophonは paras.length）
  final int level; // 2=大 3=中 4=小（percent/colophonは0）
  final String label;
  final double share; // この章の字数 ÷ 最大章字数（0..1、分量バー用）
  const TocEntry({
    required this.kind,
    required this.paraIndex,
    required this.label,
    this.level = 0,
    this.share = 0,
  });
}

/// 作品全体の目次を作る。
List<TocEntry> buildToc(Doc doc) {
  final paras = doc.paras;
  final headingIdx = <int>[
    for (var i = 0; i < paras.length; i++)
      if (paras[i].h != 0) i
  ];

  final entries = <TocEntry>[];
  if (headingIdx.isNotEmpty) {
    // 章の分量 = この見出しから次の見出しまでの字数
    final lengths = <int>[];
    for (var k = 0; k < headingIdx.length; k++) {
      final start = headingIdx[k];
      final end = k + 1 < headingIdx.length ? headingIdx[k + 1] : paras.length;
      var chars = 0;
      for (var i = start; i < end; i++) {
        chars += paras[i].plain.length;
      }
      lengths.add(chars);
    }
    final maxLen = lengths.reduce((a, b) => a > b ? a : b);
    for (var k = 0; k < headingIdx.length; k++) {
      final p = paras[headingIdx[k]];
      entries.add(TocEntry(
        kind: TocKind.heading,
        paraIndex: headingIdx[k],
        level: p.h,
        label: p.plain.trim(),
        share: maxLen == 0 ? 0 : lengths[k] / maxLen,
      ));
    }
  } else if (paras.length >= 20) {
    // 見出しが無い作品: 10%刻みの進捗ジャンプ（冒頭抜粋をラベルに）
    for (var pct = 0; pct <= 90; pct += 10) {
      var i = (paras.length * pct / 100).floor();
      // 空でない段落まで進める
      while (i < paras.length && paras[i].plain.trim().isEmpty) {
        i++;
      }
      if (i >= paras.length) break;
      final head = paras[i].plain.trim();
      entries.add(TocEntry(
        kind: TocKind.percent,
        paraIndex: i,
        label:
            '$pct%　${head.length > 16 ? '${head.substring(0, 16)}…' : head}',
      ));
    }
  }

  if (doc.colophon.trim().isNotEmpty) {
    entries.add(TocEntry(
      kind: TocKind.colophon,
      paraIndex: paras.length, // 末尾（底本表示位置）
      label: '底本',
    ));
  }
  return entries;
}
