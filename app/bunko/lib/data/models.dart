/// データモデル —— Python 側 aozorabunko の Document JSON スキーマと同一。
///
/// 一次表現は「外字・アクセント解決済みの構造化Unicodeデータ」。このモデルは
/// aozorabunko の `Document.to_dict()` と往復互換で、DBの doc 列・Dartパーサの
/// 出力のどちらも同じ形になる（作った場所によらず同じデータ）。
library;

class Seg {
  final String t; // 本文
  final String? r; // ルビ（読みデータ）
  const Seg(this.t, [this.r]);

  factory Seg.fromJson(Map<String, dynamic> j) =>
      Seg(j['t'] as String, j['r'] as String?);
  Map<String, dynamic> toJson() => r == null ? {'t': t} : {'t': t, 'r': r};
}

class Deco {
  final String t, cls, tag; // 対象文字列・CSSクラス相当・タグ種別
  const Deco(this.t, this.cls, this.tag);

  factory Deco.fromJson(Map<String, dynamic> j) =>
      Deco(j['t'] as String, j['cls'] as String, j['tag'] as String);
  Map<String, dynamic> toJson() => {'t': t, 'cls': cls, 'tag': tag};
}

class ParaImage {
  final String src;
  final int? w, h;
  final String cap;
  const ParaImage(this.src, this.w, this.h, this.cap);

  factory ParaImage.fromJson(Map<String, dynamic> j) => ParaImage(
      j['src'] as String, j['w'] as int?, j['h'] as int?,
      (j['cap'] as String?) ?? '');
  Map<String, dynamic> toJson() => {'src': src, 'w': w, 'h': h, 'cap': cap};
}

class Para {
  final List<Seg> segs;
  final int h; // 見出し 0=本文 2=大 3=中 4=小
  final String? htype; // normal / dogyo / mado
  final int indent; // 字下げ（em）
  final String? align; // 'right'（地付き・字上げ）
  final int alignOffset; // 地からN字上げ
  final int jizume;
  final List<Deco> decos;
  final ParaImage? image;

  const Para({
    required this.segs,
    this.h = 0,
    this.htype,
    this.indent = 0,
    this.align,
    this.alignOffset = 0,
    this.jizume = 0,
    this.decos = const [],
    this.image,
  });

  String get plain => segs.map((s) => s.t).join();
  String get reading => segs.map((s) => s.r ?? s.t).join();
  bool get hasRuby => segs.any((s) => s.r != null);

  factory Para.fromJson(Map<String, dynamic> j) => Para(
        segs: [for (final s in (j['seg'] as List)) Seg.fromJson(s as Map<String, dynamic>)],
        h: (j['h'] as int?) ?? 0,
        htype: j['htype'] as String?,
        indent: (j['indent'] as int?) ?? 0,
        align: j['align'] as String?,
        alignOffset: (j['align_offset'] as int?) ?? 0,
        jizume: (j['jizume'] as int?) ?? 0,
        decos: [
          for (final d in (j['deco'] as List? ?? const []))
            Deco.fromJson(d as Map<String, dynamic>)
        ],
        image: j['image'] == null
            ? null
            : ParaImage.fromJson(j['image'] as Map<String, dynamic>),
      );

  Map<String, dynamic> toJson() => {
        'seg': [for (final s in segs) s.toJson()],
        if (h != 0) 'h': h,
        if (h != 0 && htype != null) 'htype': htype,
        if (indent != 0) 'indent': indent,
        if (align != null) 'align': align,
        if (align != null && alignOffset != 0) 'align_offset': alignOffset,
        if (jizume != 0) 'jizume': jizume,
        if (decos.isNotEmpty) 'deco': [for (final d in decos) d.toJson()],
        if (image != null) 'image': image!.toJson(),
      };
}

class Doc {
  final String title, author, colophon;
  final List<Para> paras;
  const Doc({
    required this.title,
    required this.author,
    this.colophon = '',
    required this.paras,
  });

  factory Doc.fromJson(Map<String, dynamic> j) => Doc(
        title: j['title'] as String,
        author: j['author'] as String,
        colophon: (j['colophon'] as String?) ?? '',
        paras: [
          for (final p in (j['paragraphs'] as List))
            Para.fromJson(p as Map<String, dynamic>)
        ],
      );

  Map<String, dynamic> toJson() => {
        'title': title,
        'author': author,
        'colophon': colophon,
        'paragraphs': [for (final p in paras) p.toJson()],
      };
}

/// 書架メタ（SQLite works テーブルの1行）
class WorkMeta {
  final String workId, title, titleYomi, author, authorYomi, row;
  final String cardUrl, textUrl;
  final String ndc; // NDC分類（'913'/'K933'/'756 914'。空=分類なし）
  final bool readingCorpus; // NDL読みコーパス（人間の朗読由来の読みデータ）あり
  final bool copyrighted, hasDoc, hasCard;

  const WorkMeta({
    required this.workId,
    required this.title,
    required this.titleYomi,
    required this.author,
    required this.authorYomi,
    required this.row,
    required this.cardUrl,
    required this.textUrl,
    this.ndc = '',
    this.readingCorpus = false,
    required this.copyrighted,
    required this.hasDoc,
    required this.hasCard,
  });
}

/// 書架の作家見出し
class AuthorGroup {
  final String author, authorYomi, row;
  final int count;
  const AuthorGroup(this.author, this.authorYomi, this.row, this.count);
}
