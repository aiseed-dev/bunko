/// 音声読み上げ —— ルビ＝読みデータをそのままTTSへ。
///
/// 青空文庫の注記形式ならではの強み: `Para.reading` はルビを読みとして採用した
/// テキストなので、難読漢字（邪智暴虐・吹聴・傪…）を**誤読しない**。
/// 段落単位で合成し、現在段落を ValueNotifier で通知（ハイライト同期・自動スクロール）。
///
/// 対応: Android / iOS / macOS / Windows / Web（flutter_tts）。Linuxデスクトップは
/// エンジン非対応のためボタンを出さない。
library;

import 'package:flutter/foundation.dart';
import 'package:flutter_tts/flutter_tts.dart';

import '../data/models.dart';

/// このプラットフォームで読み上げが使えるか
bool get ttsSupported =>
    kIsWeb ||
    defaultTargetPlatform == TargetPlatform.android ||
    defaultTargetPlatform == TargetPlatform.iOS ||
    defaultTargetPlatform == TargetPlatform.macOS ||
    defaultTargetPlatform == TargetPlatform.windows;

class ReaderTts {
  final FlutterTts _tts = FlutterTts();

  /// 読み上げ中の段落index（null=停止中）。UIはこれを listen してハイライト。
  final ValueNotifier<int?> current = ValueNotifier(null);

  bool _playing = false;
  bool _ready = false;

  Future<void> _ensureReady() async {
    if (_ready) return;
    await _tts.setLanguage('ja-JP');
    await _tts.setSpeechRate(0.55); // 朗読向けにやや遅め
    await _tts.awaitSpeakCompletion(true);
    _ready = true;
  }

  /// 指定段落から順に読み上げる（空段落・画像はスキップ）。
  Future<void> playFrom(List<Para> paras, int startIndex) async {
    await stop();
    await _ensureReady();
    _playing = true;
    for (var i = startIndex; i < paras.length && _playing; i++) {
      final text = paras[i].reading.replaceAll(RegExp(r'[※〔〕｜]'), '').trim();
      if (text.isEmpty) continue;
      current.value = i;
      try {
        await _tts.speak(text); // awaitSpeakCompletion で読了まで待つ
      } catch (_) {
        break; // エンジン不調時は静かに停止
      }
    }
    if (_playing) {
      _playing = false;
      current.value = null; // 読了
    }
  }

  Future<void> stop() async {
    _playing = false;
    current.value = null;
    try {
      await _tts.stop();
    } catch (_) {}
  }

  void dispose() {
    stop();
    current.dispose();
  }
}
