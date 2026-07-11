/// 縦書きページめくりのテスト（キー操作・頁計算・タップゾーン）。
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:bunko/data/models.dart';
import 'package:bunko/ui/vertical_reader.dart';

Doc _longDoc() => Doc(title: 't', author: 'a', paras: [
      for (var i = 0; i < 40; i++)
        Para(segs: [Seg('これは第$i段落の本文でありますあいうえおかきくけこ')]),
    ]);

void main() {
  Future<ScrollController> pump(WidgetTester tester,
      {required ScrollController controller}) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: SizedBox(
          width: 400,
          height: 500,
          child: VerticalReader(
              doc: _longDoc(), fontSize: 16, controller: controller),
        ),
      ),
    ));
    await tester.pumpAndSettle();
    return controller;
  }

  testWidgets('←キーで次の頁（列揃えのページ幅ぶん進む）', (tester) async {
    final c = ScrollController();
    await pump(tester, controller: c);
    expect(c.offset, 0);

    await tester.sendKeyEvent(LogicalKeyboardKey.arrowLeft);
    await tester.pumpAndSettle();
    // 1頁 = floor(400 / colW) * colW（colW = 16*1.9 = 30.4 → 13列 = 395.2）
    expect(c.offset, closeTo(395.2, 1.0));

    await tester.sendKeyEvent(LogicalKeyboardKey.arrowRight); // 前の頁へ戻る
    await tester.pumpAndSettle();
    expect(c.offset, 0);
  });

  testWidgets('先頭頁より前へは戻らない・頁番号が表示される', (tester) async {
    final c = ScrollController();
    await pump(tester, controller: c);
    await tester.sendKeyEvent(LogicalKeyboardKey.arrowRight);
    await tester.pumpAndSettle();
    expect(c.offset, 0); // 先頭のまま
    expect(find.textContaining(' / '), findsOneWidget); // ノンブル
  });

  testWidgets('左端タップで次の頁', (tester) async {
    final c = ScrollController();
    await pump(tester, controller: c);
    await tester.tapAt(const Offset(30, 250)); // 左端25%以内
    await tester.pumpAndSettle();
    expect(c.offset, greaterThan(300));
  });
}
