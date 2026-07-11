/// 目次生成（buildToc・公式流=見出しのみ）の単体テスト。
library;

import 'package:flutter_test/flutter_test.dart';

import 'package:bunko/data/models.dart';
import 'package:bunko/data/toc.dart';

Para _p(String t, {int h = 0}) => Para(segs: [Seg(t)], h: h);

void main() {
  test('見出しの階層リストのみ（公式の目次パネルと同じ内容）', () {
    final doc = Doc(title: 't', author: 'a', colophon: '底本：全集', paras: [
      _p('一', h: 3),
      _p('本文' * 50),
      _p('二', h: 3),
      _p('小見出し', h: 4),
      _p('本文'),
    ]);
    final toc = buildToc(doc);
    expect(toc.length, 3); // 見出しのみ（底本・進捗などは入れない）
    expect(toc[0].label, '一');
    expect(toc[0].paraIndex, 0);
    expect(toc[0].level, 3);
    expect(toc[2].level, 4);
  });

  test('見出しの無い作品は空（公式XHTMLにも目次は出ない）', () {
    final doc = Doc(
        title: 't', author: 'a',
        paras: [for (var i = 0; i < 40; i++) _p('段落$i')]);
    expect(buildToc(doc), isEmpty);
  });
}
