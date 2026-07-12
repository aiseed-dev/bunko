/// 同人誌ひろば —— 個人出版した作者が「自分の作品を知ってもらう」ための、
/// 無償・非追跡の紹介コーナー。
///
/// 中央ホスティングはしない（本文はいつも作者のURLから取得）。ここに載る
/// リストそのものも、bunkoリポにgit管理されたJSON1枚（assets/dojinshi_directory.json）
/// ——作者がPRで1件足すだけで載る、掲載可否は人手のPRレビューが担う最小の門番。
/// 広告ネットワークは使わない（追跡・外部送信をこのアプリに持ち込まない方針を維持）。
library;

import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;

const _liveUrl =
    'https://raw.githubusercontent.com/aiseed-dev/bunko/main/assets/dojinshi_directory.json';

class DojinshiEntry {
  final String title;
  final String author;
  final String url;
  final String blurb;

  const DojinshiEntry(
      {required this.title,
      required this.author,
      required this.url,
      required this.blurb});

  factory DojinshiEntry.fromJson(Map<String, dynamic> j) => DojinshiEntry(
        title: j['title'] as String? ?? '',
        author: j['author'] as String? ?? '',
        url: j['url'] as String? ?? '',
        blurb: j['blurb'] as String? ?? '',
      );
}

List<DojinshiEntry> parseDirectory(String raw) {
  final list = jsonDecode(raw) as List;
  return list
      .map((e) => DojinshiEntry.fromJson((e as Map).cast<String, dynamic>()))
      .where((e) => e.url.isNotEmpty)
      .toList();
}

/// 最新のリポジトリ版を取りに行き、失敗（オフライン等）なら同梱版にフォールバック。
Future<List<DojinshiEntry>> loadDojinshiDirectory() async {
  try {
    final res = await http.get(Uri.parse(_liveUrl));
    if (res.statusCode == 200) return parseDirectory(res.body);
  } catch (_) {
    // オフライン等は同梱版へ
  }
  final bundled =
      await rootBundle.loadString('assets/dojinshi_directory.json');
  return parseDirectory(bundled);
}
