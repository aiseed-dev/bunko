import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:sqflite/sqflite.dart';

import '../api.dart';
import '../models.dart';

class DetailScreen extends StatefulWidget {
  final Database db;
  final Contact contact;

  const DetailScreen({super.key, required this.db, required this.contact});

  @override
  State<DetailScreen> createState() => _DetailScreenState();
}

class _DetailScreenState extends State<DetailScreen> {
  late bool _confirmed;
  late bool _handled;
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _confirmed = widget.contact.confirmed;
    _handled = widget.contact.handled;
  }

  Map<String, dynamic> get _fields {
    try {
      return jsonDecode(widget.contact.payload) as Map<String, dynamic>;
    } catch (_) {
      return {'payload': widget.contact.payload};
    }
  }

  Future<void> _confirm() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.db.update(
        'contact',
        {'confirmed': 1},
        where: 'remote_id = ?',
        whereArgs: [widget.contact.remoteId],
      );
      final config = await loadApiConfig(widget.db);
      if (config != null) {
        await ackItems(config, [widget.contact.remoteId]);
      }
      if (!mounted) return;
      setState(() => _confirmed = true);
    } catch (e) {
      setState(() => _error = '確認処理に失敗しました: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _markHandled() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.db.update(
        'contact',
        {'handled': 1},
        where: 'remote_id = ?',
        whereArgs: [widget.contact.remoteId],
      );
      if (!mounted) return;
      setState(() => _handled = true);
    } catch (e) {
      setState(() => _error = '対応済み処理に失敗しました: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('問い合わせ詳細')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('受付時刻: ${widget.contact.createdAt}'),
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (final entry in _fields.entries)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            entry.key,
                            style: const TextStyle(
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          Text('${entry.value}'),
                        ],
                      ),
                    ),
                ],
              ),
            ),
          ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: (_busy || _confirmed) ? null : _confirm,
            icon: const Icon(Icons.check),
            label: Text(_confirmed ? '確認済み' : '確認する'),
          ),
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(
              '確認すると、この問い合わせはCloudflareの受信箱から削除されます。'
              'データはこの端末に残ります。',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: (_busy || _handled) ? null : _markHandled,
            icon: const Icon(Icons.task_alt),
            label: Text(_handled ? '対応済み' : '対応済みにする'),
          ),
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(
              '返信などの対応を終えたら押します。端末内の整理用の印です。',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
        ],
      ),
    );
  }
}
