/// 追加した作品（同人誌方式） —— 各自が好きな場所で公開したURLを
/// 「開く」だけでなく、書架に恒久的に並べておくための最小の記録。
///
/// 中央の投稿サーバは持たない。ここに保存するのは本文そのものではなく
/// {url, title, author, addedAt} という「しおり」だけで、開くたびに
/// 元のURLへ本文を取りに行く（出典はいつも公開者の手元にある）。
/// SharedPreferencesはWeb（localStorage）・ネイティブ（実ファイル）の
/// どちらでも永続化されるため、db_web.dart のインメモリSQLite制約を
/// 受けない。
library;

import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

const _prefsKey = 'my_library_v1';

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
    return updated;
  }
}
