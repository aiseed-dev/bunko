/// 書架DB —— 同梱 aozora.db（メタ＝表・本文/図書カード＝JSON列）への窓口。
///
/// 設計（DESIGN.md ADR-2）: 検索・集計はSQL、細部（doc/card）はJSONのまま。
/// プラットフォーム別のオープンは条件付きインポート（io=ファイル / web=wasm）。
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:sqlite3/common.dart';

import 'db_io.dart' if (dart.library.js_interop) 'db_web.dart';
import 'models.dart';

class BunkoDb {
  final CommonDatabase _db;
  BunkoDb._(this._db);

  static Future<BunkoDb> open(Uint8List assetBytes) async =>
      BunkoDb._(await openPlatformDatabase(assetBytes));

  /// テスト用: 開き済みDBを包む
  BunkoDb.wrap(CommonDatabase db) : _db = db;

  WorkMeta _meta(Row r) => WorkMeta(
        workId: r['work_id'] as String,
        title: r['title'] as String,
        titleYomi: (r['title_yomi'] as String?) ?? '',
        author: r['author'] as String,
        authorYomi: (r['author_yomi'] as String?) ?? '',
        row: (r['row'] as String?) ?? 'その他',
        cardUrl: (r['card_url'] as String?) ?? '',
        ndc: (r['ndc'] as String?) ?? '',
        textUrl: (r['text_url'] as String?) ?? '',
        copyrighted: (r['copyrighted'] as int) != 0,
        hasDoc: r['has_doc'] as int != 0,
        hasCard: r['has_card'] as int != 0,
      );

  static const _cols = 'work_id,title,title_yomi,author,author_yomi,row,'
      'card_url,text_url,copyrighted,ndc,'
      '(doc IS NOT NULL) AS has_doc,(card IS NOT NULL) AS has_card';

  /// 書架: 作家別の作品数（よみ順）。行タブ（row）と個別かな（initials）で絞り込み。
  /// 公式サイトの総合インデックス（作家別: あ行→ア・イ・ウ・エ・オ）に対応する。
  List<AuthorGroup> authors({String? row, List<String>? initials}) {
    final conds = <String>[];
    final args = <Object?>[];
    if (row != null) {
      conds.add('row = ?');
      args.add(row);
    }
    if (initials != null && initials.isNotEmpty) {
      conds.add('substr(author_yomi,1,1) IN '
          '(${List.filled(initials.length, '?').join(',')})');
      args.addAll(initials);
    }
    final where = conds.isEmpty ? '' : 'WHERE ${conds.join(' AND ')}';
    final rs = _db.select(
        'SELECT author,author_yomi,row,COUNT(*) AS c FROM works $where '
        'GROUP BY author,author_yomi ORDER BY author_yomi',
        args);
    return [
      for (final r in rs)
        AuthorGroup(r['author'] as String, r['author_yomi'] as String,
            (r['row'] as String?) ?? 'その他', r['c'] as int)
    ];
  }

  /// 作品別インデックス（公式の「公開中 作品別一覧」相当）: 作品名よみの頭文字で絞る。
  List<WorkMeta> worksByTitleKana(List<String> initials, {int limit = 500}) {
    if (initials.isEmpty) return const [];
    final rs = _db.select(
        'SELECT $_cols FROM works WHERE substr(title_yomi,1,1) IN '
        '(${List.filled(initials.length, '?').join(',')}) '
        'ORDER BY title_yomi, title LIMIT ?',
        [...initials, limit]);
    return [for (final r in rs) _meta(r)];
  }

  /// 作品名・著者名・よみ の部分一致検索
  List<WorkMeta> search(String q, {int limit = 50}) {
    final like = '%$q%';
    final rs = _db.select(
        'SELECT $_cols FROM works WHERE title LIKE ? OR title_yomi LIKE ? '
        'OR author LIKE ? OR author_yomi LIKE ? '
        'ORDER BY (title=?) DESC, author_yomi, title_yomi LIMIT ?',
        [like, like, like, like, q, limit]);
    return [for (final r in rs) _meta(r)];
  }

  /// 作家の全作品（作品よみ順）
  List<WorkMeta> byAuthor(String author, String authorYomi) {
    final rs = _db.select(
        'SELECT $_cols FROM works WHERE author=? AND author_yomi=? '
        'ORDER BY title_yomi, title',
        [author, authorYomi]);
    return [for (final r in rs) _meta(r)];
  }

  /// 分野別: 最上位分類（0-9=NDC類・K=児童）ごとの作品数。主分類（先頭コード）で数える。
  List<(String, int)> ndcTop() {
    final rs = _db.select(
        "SELECT substr(ndc,1,1) AS c, COUNT(*) AS n FROM works "
        "WHERE ndc != '' GROUP BY c ORDER BY c");
    return [for (final r in rs) (r['c'] as String, r['n'] as int)];
  }

  /// 分野別: 最上位分類内の3桁分類（Kは'K'+3桁）ごとの作品数。
  List<(String, int)> ndcSub(String top) {
    final len = top == 'K' ? 4 : 3;
    final rs = _db.select(
        "SELECT substr(ndc,1,?) AS c, COUNT(*) AS n FROM works "
        "WHERE ndc LIKE ? GROUP BY c ORDER BY c",
        [len, '$top%']);
    return [for (final r in rs) (r['c'] as String, r['n'] as int)];
  }

  /// 分野別: 分類コード（'9'類全体 or '913' or 'K913'）の作品一覧（よみ順）。
  List<WorkMeta> worksByNdc(String prefix, {int limit = 3000}) {
    final rs = _db.select(
        'SELECT $_cols FROM works WHERE ndc LIKE ? '
        'ORDER BY title_yomi, title LIMIT ?',
        ['$prefix%', limit]);
    return [for (final r in rs) _meta(r)];
  }

  WorkMeta? work(String workId) {
    final rs =
        _db.select('SELECT $_cols FROM works WHERE work_id=?', [workId]);
    return rs.isEmpty ? null : _meta(rs.first);
  }

  /// 本文（doc列のJSON）。未取得なら null。
  Doc? loadDoc(String workId) {
    final rs = _db.select('SELECT doc FROM works WHERE work_id=?', [workId]);
    if (rs.isEmpty || rs.first['doc'] == null) return null;
    return Doc.fromJson(
        jsonDecode(rs.first['doc'] as String) as Map<String, dynamic>);
  }

  void saveDoc(String workId, Doc doc) {
    _db.execute('UPDATE works SET doc=? WHERE work_id=?',
        [jsonEncode(doc.toJson()), workId]);
  }

  /// 図書カード詳細（card列のJSON）。未取得なら null。
  Map<String, dynamic>? loadCard(String workId) {
    final rs = _db.select('SELECT card FROM works WHERE work_id=?', [workId]);
    if (rs.isEmpty || rs.first['card'] == null) return null;
    return jsonDecode(rs.first['card'] as String) as Map<String, dynamic>;
  }

  void saveCard(String workId, Map<String, dynamic> card) {
    _db.execute('UPDATE works SET card=? WHERE work_id=?',
        [jsonEncode(card), workId]);
  }

  ({int works, int authors, int docs}) stats() {
    final r = _db.select('SELECT COUNT(*) AS n,'
        'COUNT(DISTINCT author||author_yomi) AS a,'
        'SUM(doc IS NOT NULL) AS d FROM works').first;
    return (works: r['n'] as int, authors: r['a'] as int,
        docs: (r['d'] as int?) ?? 0);
  }
}
