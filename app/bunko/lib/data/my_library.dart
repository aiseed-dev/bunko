/// 追加した作品（同人誌方式） —— 各自が好きな場所で公開したURLを
/// 「開く」だけでなく、書架に恒久的に並べておくための最小の記録。
///
/// 中央の投稿サーバは持たない。ここに保存するのは本文そのものではなく
/// {url, title, author, addedAt} という「しおり」だけで、開くたびに
/// 元のURLへ本文を取りに行く（出典はいつも公開者の手元にある）。
/// SharedPreferencesはWeb（localStorage）・ネイティブ（実ファイル）の
/// どちらでも永続化されるため、db_web.dart のインメモリSQLite制約を
/// 受けない。
///
/// 「手元に保存」（saveBody/loadBody）は任意のオプトイン: 作者が公開を
/// やめた・書籍化のため取り下げた後も、ダウンロード済みの読者だけは
/// 読み続けられるようにする（購入後の作品でも同じ理屈が要る、という
/// 発想の延長）。既定は保存しない＝しおりだけのまま軽量に保つ。
library;

import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

const _prefsKey = 'my_library_v1';
const _bodyPrefix = 'my_library_body_v1:';

class AddedWork {
  final String url;
  final String title;
  final String author;
  final String addedAt; // ISO8601（呼び出し側が付与）

  const AddedWork(
      {required this.url,
      required this.title,
      required this.author,
      required this.addedAt});

  factory AddedWork.fromJson(Map<String, dynamic> j) => AddedWork(
        url: j['url'] as String,
        title: j['title'] as String? ?? '',
        author: j['author'] as String? ?? '',
        addedAt: j['addedAt'] as String? ?? '',
      );

  Map<String, dynamic> toJson() =>
      {'url': url, 'title': title, 'author': author, 'addedAt': addedAt};
}

class MyLibrary {
  static Future<List<AddedWork>> load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_prefsKey);
    if (raw == null || raw.isEmpty) return [];
    final list = jsonDecode(raw) as List;
    return list
        .map((e) => AddedWork.fromJson((e as Map).cast<String, dynamic>()))
        .toList();
  }

  static Future<void> _save(List<AddedWork> works) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
        _prefsKey, jsonEncode(works.map((w) => w.toJson()).toList()));
  }

  static Future<bool> contains(String url) async {
    final list = await load();
    return list.any((w) => w.url == url);
  }

  static Future<List<AddedWork>> add(AddedWork work) async {
    final list = await load();
    if (list.any((w) => w.url == work.url)) return list;
    final updated = [...list, work];
    await _save(updated);
    return updated;
  }

  static Future<List<AddedWork>> remove(String url) async {
    final list = await load();
    final updated = list.where((w) => w.url != url).toList();
    await _save(updated);
    await clearBody(url);
    return updated;
  }

  /// 本文（Document JSON文字列）を手元に保存。作者が公開をやめた後も
  /// 保存済みの読者だけは読み続けられる。著作権の扱いは**作者の選択**
  /// （Doc.license。例 'CC BY 4.0'／'CC0'）——空なら「作者に著作権があり
  /// 明示の許可なく複製・配布はできない」が既定（無方式主義で自動的に
  /// 保護される権利）。DRM等の技術制限はせず、呼び出し側が保存時に
  /// その旨（doc.licenseの内容）を明示する運用とする。
  static Future<void> saveBody(String url, String docJson) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('$_bodyPrefix$url', docJson);
  }

  static Future<String?> loadBody(String url) async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString('$_bodyPrefix$url');
  }

  static Future<bool> hasBody(String url) async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.containsKey('$_bodyPrefix$url');
  }

  static Future<void> clearBody(String url) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('$_bodyPrefix$url');
  }
}
