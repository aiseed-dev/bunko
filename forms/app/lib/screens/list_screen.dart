import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:sqflite/sqflite.dart';

import '../api.dart';
import '../models.dart';
import '../sync.dart';
import 'detail_screen.dart';
import 'help_screen.dart';
import 'settings_screen.dart';

enum ContactFilter { unconfirmed, confirmed, handled }

extension on ContactFilter {
  String get label => switch (this) {
    ContactFilter.unconfirmed => '未確認',
    ContactFilter.confirmed => '確認済み',
    ContactFilter.handled => '対応済み',
  };

  String get where => switch (this) {
    ContactFilter.unconfirmed => 'confirmed = 0',
    ContactFilter.confirmed => 'confirmed = 1 AND handled = 0',
    ContactFilter.handled => 'handled = 1',
  };
}

const _syncInterval = Duration(hours: 3);

class ListScreen extends StatefulWidget {
  final Database db;

  const ListScreen({super.key, required this.db});

  @override
  State<ListScreen> createState() => _ListScreenState();
}

class _ListScreenState extends State<ListScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;
  Timer? _timer;
  int _reloadToken = 0;
  bool _syncing = false;
  String? _syncError;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _timer = Timer.periodic(_syncInterval, (_) => _sync());
    WidgetsBinding.instance.addPostFrameCallback((_) => _sync());
  }

  @override
  void dispose() {
    _timer?.cancel();
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _sync() async {
    if (_syncing) return;
    final config = await loadApiConfig(widget.db);
    if (config == null) return;
    setState(() {
      _syncing = true;
      _syncError = null;
    });
    try {
      await pullItems(widget.db, config);
    } catch (e) {
      _syncError = '取得に失敗しました: $e';
    } finally {
      if (mounted) {
        setState(() {
          _syncing = false;
          _reloadToken++;
        });
        if (_syncError != null) {
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(SnackBar(content: Text(_syncError!)));
        }
      }
    }
  }

  Future<void> _openSettings() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => SettingsScreen(db: widget.db),
      ),
    );
    _sync();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('FormRescue'),
        bottom: TabBar(
          controller: _tabController,
          tabs: [
            for (final f in ContactFilter.values) Tab(text: f.label),
          ],
        ),
        actions: [
          IconButton(
            icon: _syncing
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.refresh),
            onPressed: _syncing ? null : _sync,
            tooltip: '取得',
          ),
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: _openSettings,
            tooltip: '設定',
          ),
          IconButton(
            icon: const Icon(Icons.help_outline),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const HelpScreen()),
            ),
            tooltip: 'このアプリについて',
          ),
        ],
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          for (final f in ContactFilter.values)
            _ContactListView(
              db: widget.db,
              filter: f,
              reloadToken: _reloadToken,
              onChanged: () => setState(() => _reloadToken++),
            ),
        ],
      ),
    );
  }
}

class _ContactListView extends StatefulWidget {
  final Database db;
  final ContactFilter filter;
  final int reloadToken;
  final VoidCallback onChanged;

  const _ContactListView({
    required this.db,
    required this.filter,
    required this.reloadToken,
    required this.onChanged,
  });

  @override
  State<_ContactListView> createState() => _ContactListViewState();
}

class _ContactListViewState extends State<_ContactListView> {
  List<Contact> _contacts = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(covariant _ContactListView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.reloadToken != widget.reloadToken) {
      _load();
    }
  }

  Future<void> _load() async {
    final rows = await widget.db.query(
      'contact',
      where: widget.filter.where,
      orderBy: 'created_at DESC',
    );
    if (!mounted) return;
    setState(() {
      _contacts = rows.map(Contact.fromRow).toList();
      _loading = false;
    });
  }

  String _preview(String payload) {
    try {
      final json = jsonDecode(payload) as Map<String, dynamic>;
      final firstValue = json.values.firstWhere(
        (v) => v is String && v.trim().isNotEmpty,
        orElse: () => '',
      );
      return firstValue.toString();
    } catch (_) {
      return payload;
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_contacts.isEmpty) {
      final message = switch (widget.filter) {
        ContactFilter.unconfirmed =>
          '未確認の問い合わせはありません。\n\n'
              'サイトのフォームから送信があると、起動時・「取得」ボタン・'
              '数時間おきの自動取得で、ここに表示されます。',
        ContactFilter.confirmed => '確認済み(未対応)の問い合わせはありません。',
        ContactFilter.handled => '対応済みの問い合わせはありません。',
      };
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(message, textAlign: TextAlign.center),
        ),
      );
    }
    return ListView.separated(
      itemCount: _contacts.length,
      separatorBuilder: (_, _) => const Divider(height: 1),
      itemBuilder: (context, index) {
        final contact = _contacts[index];
        return ListTile(
          title: Text(contact.email?.isNotEmpty == true
              ? contact.email!
              : '(メールアドレスなし)'),
          subtitle: Text(
            '${contact.createdAt}\n${_preview(contact.payload)}',
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
          isThreeLine: true,
          onTap: () async {
            await Navigator.of(context).push(
              MaterialPageRoute(
                builder: (_) =>
                    DetailScreen(db: widget.db, contact: contact),
              ),
            );
            widget.onChanged();
          },
        );
      },
    );
  }
}
