/// 正本の取得 —— GitHubミラーの静的ファイルのみ・公式サーバーには触れない。
///
/// 注記付きテキスト zip → Shift_JIS復号 → 注記パース → Doc（DBのdoc列へ保存）。
/// 図書カード html → parseCard → card列へ保存。raw.githubusercontent.com は
/// CORS許可(*)なので Flutter Web からも同じコードで取得できる。
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:archive/archive.dart';
import 'package:http/http.dart' as http;

import 'aozora_parser.dart';
import 'card_parser.dart';
import 'db.dart';
import 'models.dart';
import 'sjis.dart';

const mirror = 'https://raw.githubusercontent.com/aozorabunko/aozorabunko/master/';
final _aozoraUrlRe = RegExp(r'https?://www\.aozora\.gr\.jp/(cards/.+)');

String toMirror(String url) {
  final m = _aozoraUrlRe.firstMatch(url);
  return m != null ? '$mirror${m[1]}' : url;
}

class Fetcher {
  final BunkoDb db;
  final AozoraParser parser;
  final SjisDecoder sjis;
  Fetcher({required this.db, required this.parser, required this.sjis});

  /// 本文を取得してパースし、doc列へ保存して返す。
  Future<Doc> fetchDoc(WorkMeta w) async {
    final url = toMirror(w.textUrl);
    final res = await http.get(Uri.parse(url));
    if (res.statusCode != 200) {
      throw Exception('取得できませんでした (${res.statusCode}): $url');
    }
    var bytes = res.bodyBytes;
    if (bytes.length >= 2 && bytes[0] == 0x50 && bytes[1] == 0x4B) {
      final zip = ZipDecoder().decodeBytes(bytes);
      final txt = zip.files.firstWhere((f) => f.name.endsWith('.txt'));
      bytes = Uint8List.fromList(txt.content as List<int>);
    }
    final text = sjis.decode(bytes);
    final imageBase = '${url.substring(0, url.lastIndexOf('/'))}/';
    final doc = parser.parse(text, imageBase: imageBase);
    db.saveDoc(w.workId, doc);
    return doc;
  }

  /// 図書カード詳細を取得して card列へ保存して返す。
  Future<Map<String, dynamic>> fetchCard(WorkMeta w) async {
    final url = toMirror(w.cardUrl);
    final res = await http.get(Uri.parse(url));
    if (res.statusCode != 200) {
      throw Exception('図書カードを取得できませんでした (${res.statusCode})');
    }
    String html;
    try {
      html = utf8.decode(res.bodyBytes); // ミラーはUTF-8
    } on FormatException {
      html = sjis.decode(res.bodyBytes); // 念のためのフォールバック
    }
    final card = parseCard(html);
    db.saveCard(w.workId, card);
    return card;
  }
}
