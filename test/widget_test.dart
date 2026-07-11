import 'package:flutter_test/flutter_test.dart';

import 'package:bunko/data/models.dart';
import 'package:bunko/theme.dart';
import 'package:flutter/material.dart';
import 'package:bunko/ui/ruby_text.dart';

void main() {
  testWidgets('ルビ段落が描画される', (tester) async {
    const para = Para(segs: [
      Seg('必ず、かの'),
      Seg('邪智暴虐', 'じゃちぼうぎゃく'),
      Seg('の王を除かなければならぬ'),
    ]);
    await tester.pumpWidget(MaterialApp(
      theme: bunkoTheme(),
      home: Scaffold(
        body: Text.rich(TextSpan(
            children: paragraphSpans(
                para, const TextStyle(fontSize: 18, height: 1.9)))),
      ),
    ));
    expect(find.text('邪智暴虐'), findsOneWidget);
    expect(find.text('じゃちぼうぎゃく'), findsOneWidget);
  });
}
