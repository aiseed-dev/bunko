/// 目次 —— 青空文庫公式XHTMLの目次パネルに合わせ、**見出しの階層リストのみ**。
/// （大見出し／中見出し／小見出しをインデントで表す。装飾は加えない）
library;

import 'models.dart';

class TocEntry {
  final int paraIndex; // ジャンプ先の段落index
  final int level; // 2=大 3=中 4=小
  final String label;
  const TocEntry(
      {required this.paraIndex, required this.level, required this.label});
}

/// 見出しの一覧（公式の目次と同じ内容）。見出しの無い作品は空リスト。
List<TocEntry> buildToc(Doc doc) => [
      for (var i = 0; i < doc.paras.length; i++)
        if (doc.paras[i].h != 0)
          TocEntry(
              paraIndex: i,
              level: doc.paras[i].h,
              label: doc.paras[i].plain.trim()),
    ];
