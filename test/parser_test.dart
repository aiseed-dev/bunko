/// 注記パーサ（Dart移植）の単体テスト。
/// Python版 aozorabunko のテストと同じ判定を移植し、両実装の互換を担保する。
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';

import 'package:bunko/data/aozora_parser.dart';
import 'package:bunko/data/models.dart';
import 'package:bunko/data/sjis.dart';

late AozoraParser parser;

void main() {
  setUpAll(() {
    final jis = jsonDecode(File('assets/jis2ucs.json').readAsStringSync())
        as Map<String, dynamic>;
    parser = AozoraParser(jis.cast<String, String>());
  });

  group('外字', () {
    test('面区点 1-06-75 → ☃（雪だるま）', () {
      expect(parser.resolveGaiji('※［＃「雪だるま」、1-06-75］'), '☃');
    });
    test('第3水準・非ゼロ詰め表記', () {
      final r = parser.resolveGaiji('袁※［＃「にんべん＋參」、第4水準2-1-79］は');
      expect(r, '袁傪は');
    });
    test('U+ 直接指定', () {
      expect(parser.resolveGaiji('※［＃「はしごだか」、U+9AD9］'), '髙');
    });
    test('未解決は〓（本文から欠落させない）', () {
      expect(parser.resolveGaiji('※［＃「合成」、非0213外字］'), geta);
    });
  });

  group('パース', () {
    Doc p(String body) => parser.parse('題\n著\n\n$body\n');

    test('ルビ（漢字連続・｜複合語）', () {
      final d = p('邪智暴虐《じゃちぼうぎゃく》の王。｜世界中《せかいじゅう》');
      final segs = d.paras[0].segs;
      expect(segs[0].t, '邪智暴虐');
      expect(segs[0].r, 'じゃちぼうぎゃく');
      expect(d.paras[0].reading.contains('じゃちぼうぎゃく'), true);
      expect(segs.any((s) => s.t == '世界中' && s.r == 'せかいじゅう'), true);
    });

    test('見出し3形式', () {
      expect(p('序章［＃「序章」は大見出し］').paras[0].h, 2);
      expect(p('［＃中見出し］一［＃中見出し終わり］').paras[0].h, 3);
      final mado = p('窓［＃「窓」は窓小見出し］').paras[0];
      expect((mado.h, mado.htype), (4, 'mado'));
    });

    test('字下げ・地付き', () {
      expect(p('［＃３字下げ］本文').paras[0].indent, 3);
      expect(p('［＃地から２字上げ］署名').paras[0].align, 'right');
      final block = parser.parse(
          '題\n著\n\n［＃ここから２字下げ］\n中\n［＃ここで字下げ終わり］\n外\n');
      expect(block.paras[0].indent, 2);
      expect(block.paras[1].indent, 0);
    });

    test('傍点・太字', () {
      final d = p('強調［＃「強調」に傍点］と重要［＃「重要」は太字］');
      expect(d.paras[0].decos.map((x) => (x.t, x.cls)).toList(),
          [('強調', 'sesame_dot'), ('重要', 'futoji')]);
      expect(d.paras[0].plain, '強調と重要');
    });

    test('挿絵', () {
      final d = parser.parse('題\n著\n\n［＃挿絵（fig1.png、横40×縦50）入る］\n',
          imageBase: 'https://example.com/files/');
      final img = d.paras[0].image!;
      expect(img.src, 'https://example.com/files/fig1.png');
      expect((img.w, img.h), (40, 50));
    });

    test('底本の分離と未対応注記の除去', () {
      final d = parser.parse('題\n著\n\n本文［＃ページの左右中央］です。\n\n底本：全集\n');
      expect(d.paras[0].plain, '本文です。');
      expect(d.colophon, '底本：全集');
    });

    test('JSON往復（Python版スキーマ互換）', () {
      final d = p('走れ［＃「走れ」に傍点］メロス《めろす》');
      final round = Doc.fromJson(
          jsonDecode(jsonEncode(d.toJson())) as Map<String, dynamic>);
      expect(round.paras[0].plain, d.paras[0].plain);
      expect(round.paras[0].decos.length, 1);
    });
  });

  group('Shift_JIS復号', () {
    test('cp932.bin で日本語が復号できる', () {
      final table = File('assets/cp932.bin').readAsBytesSync();
      final dec = SjisDecoder(ByteData.sublistView(table));
      // 「走れメロス」の Shift_JIS バイト列
      final bytes = [0x91, 0x96, 0x82, 0xEA, 0x83, 0x81, 0x83, 0x8D, 0x83, 0x58];
      expect(dec.decode(Uint8List.fromList(bytes)), '走れメロス');
    });
  });
}
