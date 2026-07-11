/// 目次生成（buildToc）の単体テスト。
library;

import 'package:flutter_test/flutter_test.dart';

import 'package:bunko/data/models.dart';
import 'package:bunko/data/toc.dart';

Para _p(String t, {int h = 0}) => Para(segs: [Seg(t)], h: h);

void main() {
  test('見出しがある作品: 階層・分量バー・底本', () {
    final doc = Doc(title: 't', author: 'a', colophon: '底本：全集', paras: [
      _p('一', h: 3),
      _p('あ' * 100),
      _p('二', h: 3),
      _p('い' * 50),
      _p('小見出し', h: 4),
      _p('う' * 10),
    ]);
    final toc = buildToc(doc);
    expect(toc.length, 4); // 見出し3 + 底本
    expect(toc[0].kind, TocKind.heading);
    expect(toc[0].label, '一');
    expect(toc[0].paraIndex, 0);
    expect(toc[0].share, 1.0); // 最長の章
    expect(toc[1].share, closeTo((50 + 4) / (100 + 1), 0.05)); // 二の章はおよそ半分
    expect(toc[2].level, 4); // 小見出し
    expect(toc.last.kind, TocKind.colophon);
    expect(toc.last.paraIndex, doc.paras.length);
  });

  test('見出しの無い長編: 進捗ジャンプ（10%刻み・冒頭抜粋）', () {
    final doc = Doc(
        title: 't',
        author: 'a',
        paras: [for (var i = 0; i < 40; i++) _p('第$i段落のテキストです')]);
    final toc = buildToc(doc);
    expect(toc.length, 10); // 0%〜90%
    expect(toc.first.kind, TocKind.percent);
    expect(toc.first.paraIndex, 0);
    expect(toc.first.label, startsWith('0%　第0段落'));
    expect(toc[5].paraIndex, 20); // 50% → 40段落の半分
  });

  test('見出しなし・短編: 目次なし', () {
    final doc =
        Doc(title: 't', author: 'a', paras: [for (var i = 0; i < 5; i++) _p('短い')]);
    expect(buildToc(doc), isEmpty);
  });
}
