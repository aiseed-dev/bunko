/// 文庫の意匠 —— 和紙の生成りに墨の本文、差し色は朱ひとつ。
/// examples の書架/読書ビューア（Web版）と同じ設計言語。本文はIPAex明朝
/// （JIS X 0213全外字を含む）1フォントで、外字も実Unicode文字のまま描く。
library;

import 'package:flutter/material.dart';

abstract final class Sumi {
  static const paper = Color(0xFFE7E2D4);
  static const paperHi = Color(0xFFEEE9DC);
  static const ink = Color(0xFF221F19);
  static const inkSoft = Color(0xFF4A4437);
  static const shu = Color(0xFFA8392A); // 朱
  static const muted = Color(0xFF8C846E);
  static const rule = Color(0xFFD0C7B1);
}

ThemeData bunkoTheme() {
  final base = ThemeData(
    useMaterial3: true,
    fontFamily: 'IPAexMincho',
    colorScheme: ColorScheme.fromSeed(
      seedColor: Sumi.shu,
      primary: Sumi.shu,
      surface: Sumi.paper,
      onSurface: Sumi.ink,
    ),
    scaffoldBackgroundColor: Sumi.paper,
  );
  return base.copyWith(
    appBarTheme: const AppBarTheme(
      backgroundColor: Sumi.paperHi,
      foregroundColor: Sumi.ink,
      elevation: 0,
      surfaceTintColor: Colors.transparent,
    ),
    dividerTheme: const DividerThemeData(color: Sumi.rule, thickness: 1),
    textTheme: base.textTheme.apply(
      bodyColor: Sumi.ink,
      displayColor: Sumi.ink,
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Sumi.paperHi,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(999),
        borderSide: const BorderSide(color: Sumi.rule),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(999),
        borderSide: const BorderSide(color: Sumi.rule),
      ),
      isDense: true,
    ),
  );
}
