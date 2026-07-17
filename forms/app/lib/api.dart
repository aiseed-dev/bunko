import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:sqflite/sqflite.dart';

import 'db.dart';

class ApiConfig {
  final String workerUrl;
  final String pullToken;

  ApiConfig({required this.workerUrl, required this.pullToken});

  String get itemsUrl => '$workerUrl/items';
  String get ackUrl => '$workerUrl/ack';
}

class RemoteItem {
  final int id;
  final String createdAt;
  final String? email;
  final String payload;

  RemoteItem({
    required this.id,
    required this.createdAt,
    required this.email,
    required this.payload,
  });

  factory RemoteItem.fromJson(Map<String, dynamic> json) {
    final rawPayload = json['payload'];
    final payload = rawPayload is String ? rawPayload : jsonEncode(rawPayload);
    return RemoteItem(
      id: json['id'] as int,
      createdAt: json['created_at'] as String,
      email: json['email'] as String?,
      payload: payload,
    );
  }
}

class ApiException implements Exception {
  final String message;
  ApiException(this.message);
  @override
  String toString() => message;
}

Future<ApiConfig?> loadApiConfig(Database db) async {
  final url = await getSetting(db, 'worker_url');
  final token = await getSetting(db, 'pull_token');
  if (url == null || token == null) return null;
  return ApiConfig(workerUrl: url, pullToken: token);
}

/// Server caps a page at 500; keep in sync with the worker.js /items spec.
const int itemsPageLimit = 500;

/// Fetches one page of /items: rows with id > [after], ascending, up to [limit].
/// The caller pages by advancing [after] to the last id it received.
Future<List<RemoteItem>> fetchItemsPage(
  ApiConfig config, {
  required int after,
  int limit = itemsPageLimit,
}) async {
  final uri = Uri.parse(config.itemsUrl).replace(
    queryParameters: {'after': '$after', 'limit': '$limit'},
  );
  final res = await http.get(
    uri,
    headers: {'Authorization': 'Bearer ${config.pullToken}'},
  );
  if (res.statusCode != 200) {
    throw ApiException('/items failed: HTTP ${res.statusCode}');
  }
  final body = jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
  final items = (body['items'] as List<dynamic>? ?? [])
      .cast<Map<String, dynamic>>()
      .map(RemoteItem.fromJson)
      .toList();
  return items;
}

Future<int> ackItems(ApiConfig config, List<int> ids) async {
  if (ids.isEmpty) return 0;
  final res = await http.post(
    Uri.parse(config.ackUrl),
    headers: {
      'Authorization': 'Bearer ${config.pullToken}',
      'Content-Type': 'application/json',
    },
    body: jsonEncode({'ids': ids}),
  );
  if (res.statusCode != 200) {
    throw ApiException('/ack failed: HTTP ${res.statusCode}');
  }
  final body = jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
  return (body['deleted'] as int?) ?? ids.length;
}
