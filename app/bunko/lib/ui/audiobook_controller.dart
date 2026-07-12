/// 朗読パックの再生 —— 工房で事前合成した Opus＋段落タイミング manifest。
///
/// パックは配信ディレクトリの `audiobooks/{workId}.audiobook.json`（＋音声）に
/// 置く。manifest の paras[{i,start,dur}] で再生位置→段落を引き、読み上げ
/// （TTS）と同じ `ValueNotifier<int?>` で段落ハイライト・自動追従に繋がる。
/// パックが無い作品ではボタン自体が出ない（load が false）。
library;

import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:just_audio/just_audio.dart';

class AudiobookPara {
  final int i; // Document の段落 index
  final double start, dur; // 秒
  const AudiobookPara(this.i, this.start, this.dur);
}

class Audiobook {
  final String title, voice, audioUrl;
  final double total;
  final List<AudiobookPara> paras;
  const Audiobook(
      {required this.title,
      required this.voice,
      required this.audioUrl,
      required this.total,
      required this.paras});
}

class ReaderAudiobook {
  final AudioPlayer _player = AudioPlayer();

  /// 再生中の段落 index（停止中は null）。TTSの current と同じ約束。
  final ValueNotifier<int?> current = ValueNotifier(null);
  Audiobook? book;

  bool get available => book != null;
  bool get playing => _player.playing;
  Duration get position => _player.position;
  Stream<Duration> get positionStream => _player.positionStream;
  Stream<PlayerState> get stateStream => _player.playerStateStream;

  /// パックを探して読み込む。無ければ false（ボタン非表示に）。
  Future<bool> load(String workId) async {
    try {
      final base = Uri.base.resolve('audiobooks/');
      final res = await http.get(base.resolve('$workId.audiobook.json'));
      if (res.statusCode != 200) return false;
      final m = jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
      book = Audiobook(
        title: (m['title'] as String?) ?? '',
        voice: (m['voice'] as String?) ?? '',
        audioUrl: base.resolve(m['audio'] as String).toString(),
        total: (m['total'] as num).toDouble(),
        paras: [
          for (final p in (m['paras'] as List))
            AudiobookPara((p['i'] as num).toInt(), (p['start'] as num).toDouble(),
                (p['dur'] as num).toDouble()),
        ],
      );
      await _player.setUrl(book!.audioUrl);
      _player.positionStream.listen(_onPosition);
      _player.playerStateStream.listen((s) {
        if (s.processingState == ProcessingState.completed) {
          _player.pause();
          _player.seek(Duration.zero);
          current.value = null;
        } else if (!s.playing) {
          current.value = null; // 一時停止でハイライトを消す
        }
      });
      return true;
    } catch (_) {
      return false; // 非対応プラットフォーム・パック無し・オフライン
    }
  }

  void _onPosition(Duration d) {
    final b = book;
    if (b == null || !_player.playing) return;
    final t = d.inMicroseconds / 1e6;
    int? cur;
    for (final p in b.paras) {
      if (p.start <= t + 0.05) {
        cur = p.i;
      } else {
        break;
      }
    }
    if (current.value != cur) current.value = cur;
  }

  Future<void> toggle() =>
      _player.playing ? _player.pause() : _player.play();

  Future<void> seek(Duration d) => _player.seek(d);

  /// 段落から再生位置へ（目次ジャンプの音声側シーク）。
  Future<void> seekPara(int paraIndex) async {
    final b = book;
    if (b == null) return;
    AudiobookPara? target;
    for (final p in b.paras) {
      if (p.i <= paraIndex) target = p;
    }
    if (target != null) {
      await _player.seek(
          Duration(microseconds: (target.start * 1e6).round()));
    }
  }

  Future<void> stop() async {
    await _player.pause();
    await _player.seek(Duration.zero);
    current.value = null;
  }

  void dispose() {
    _player.dispose();
    current.dispose();
  }
}
