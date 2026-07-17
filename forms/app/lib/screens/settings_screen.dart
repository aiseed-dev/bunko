import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:sqflite/sqflite.dart';

import '../db.dart';
import 'help_screen.dart';
import 'list_screen.dart';

/// deploy.py encodes the QR payload as `{"url": "...", "token": "..."}`.
bool get qrScanSupported =>
    !kIsWeb && (Platform.isAndroid || Platform.isIOS || Platform.isMacOS);

class SettingsScreen extends StatefulWidget {
  final Database db;
  final bool isInitialSetup;

  const SettingsScreen({
    super.key,
    required this.db,
    this.isInitialSetup = false,
  });

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _urlController = TextEditingController();
  final _tokenController = TextEditingController();
  String? _error;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _loadExisting();
  }

  Future<void> _loadExisting() async {
    final url = await getSetting(widget.db, 'worker_url');
    final token = await getSetting(widget.db, 'pull_token');
    if (!mounted) return;
    setState(() {
      _urlController.text = url ?? '';
      _tokenController.text = token ?? '';
    });
  }

  @override
  void dispose() {
    _urlController.dispose();
    _tokenController.dispose();
    super.dispose();
  }

  void _applyQrPayload(String raw) {
    try {
      final json = jsonDecode(raw) as Map<String, dynamic>;
      final url = json['url'] as String?;
      final token = json['token'] as String?;
      if (url == null || token == null) {
        throw const FormatException('url/token が見つかりません');
      }
      if (!url.startsWith('https://')) {
        throw const FormatException('URLはhttps://で始まる必要があります');
      }
      setState(() {
        _urlController.text = url;
        _tokenController.text = token;
        _error = null;
      });
    } catch (e) {
      setState(() => _error = 'QRの読み取りに失敗しました: $e');
    }
  }

  Future<void> _scanQr() async {
    final result = await Navigator.of(context).push<String>(
      MaterialPageRoute(builder: (_) => const _QrScanPage()),
    );
    if (result != null) {
      _applyQrPayload(result);
    }
  }

  Future<void> _save() async {
    final url = _urlController.text.trim();
    final token = _tokenController.text.trim();
    if (url.isEmpty || token.isEmpty) {
      setState(() => _error = 'Worker URLとPULL_TOKENの両方を入力してください');
      return;
    }
    if (!url.startsWith('https://')) {
      setState(() => _error = 'URLはhttps://で始まる必要があります');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    final normalizedUrl = url.endsWith('/')
        ? url.substring(0, url.length - 1)
        : url;
    await setSetting(widget.db, 'worker_url', normalizedUrl);
    await setSetting(widget.db, 'pull_token', token);
    if (!mounted) return;
    setState(() => _saving = false);
    if (widget.isInitialSetup) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => ListScreen(db: widget.db)),
      );
    } else {
      Navigator.of(context).pop(true);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('設定')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (widget.isInitialSetup) ...[
            Text(
              'FormRescue へようこそ',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 12),
            const Text(
              'FormRescue は、WordPressの問い合わせフォームに届いたデータを、'
              'Cloudflare上の受信箱から引き取って手元で管理するアプリです。'
              'データはこの端末の中にだけ保存されます。',
            ),
            const SizedBox(height: 8),
            const Text(
              'はじめるには、受信箱を設置したとき(deploy.py または cf-publish の'
              '実行時)に表示された Worker URL と PULL_TOKEN を設定します。'
              '手元にない場合は、受信箱を設置した人に確認してください。',
            ),
            const SizedBox(height: 8),
            Text(
              qrScanSupported
                  ? 'deploy.py が表示したQRコードを下のボタンから読み取ると、'
                        '二つとも自動で入力されます。'
                  : 'deploy.py の出力から Worker URL と PULL_TOKEN をコピーして、'
                        '下の欄に貼り付けてください。'
                        '(QRコードでの読み取りは Android/iOS 版で使えます)',
            ),
            TextButton.icon(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const HelpScreen()),
              ),
              icon: const Icon(Icons.help_outline),
              label: const Text('詳しい説明を見る'),
            ),
            const Divider(height: 24),
          ],
          if (qrScanSupported) ...[
            FilledButton.icon(
              onPressed: _scanQr,
              icon: const Icon(Icons.qr_code_scanner),
              label: const Text('QRコードを読み取る'),
            ),
            const SizedBox(height: 24),
          ],
          TextField(
            controller: _urlController,
            decoration: const InputDecoration(
              labelText: 'Worker URL',
              hintText: 'https://xxxx.workers.dev',
              helperText: '受信箱(Cloudflare Worker)のURL',
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _tokenController,
            decoration: const InputDecoration(
              labelText: 'PULL_TOKEN',
              helperText: '受信箱からデータを取得するための鍵。deploy.pyが発行したもの',
            ),
            obscureText: true,
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
          FilledButton(
            onPressed: _saving ? null : _save,
            child: Text(_saving ? '保存中...' : '保存'),
          ),
        ],
      ),
    );
  }
}

class _QrScanPage extends StatelessWidget {
  const _QrScanPage();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('QRコードを読み取る')),
      body: MobileScanner(
        onDetect: (capture) {
          final barcodes = capture.barcodes;
          if (barcodes.isEmpty) return;
          final value = barcodes.first.rawValue;
          if (value != null) {
            Navigator.of(context).pop(value);
          }
        },
      ),
    );
  }
}
