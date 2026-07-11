/// 青空文庫 注記付きテキスト → Doc（Unicode構造化データ）
///
/// Python 側 aozorabunko/parser.py の Dart 移植。出力スキーマは同一（models.dart）。
/// 対応注記: ルビ・外字（JIS X 0213 面区点/U+ → 実Unicode文字）・見出し3形式・
/// 字下げ/地付き/字詰め（ブロック含む）・傍点/傍線/太字等の装飾・挿絵。
/// （欧文アクセント〔e'〕分解は v1 未対応 —— 〔〕のまま表示される）
library;

import 'models.dart';

const geta = '〓'; // 未解決外字の代替

// ── 装飾の対応表（aozorabunko/decorate.py = aozora2html command_table 由来）──
const Map<String, (String, String)> commandTable = {
  '傍点': ('sesame_dot', 'em'),
  '白ゴマ傍点': ('white_sesame_dot', 'em'),
  '丸傍点': ('black_circle', 'em'),
  '白丸傍点': ('white_circle', 'em'),
  '黒三角傍点': ('black_up-pointing_triangle', 'em'),
  '白三角傍点': ('white_up-pointing_triangle', 'em'),
  '二重丸傍点': ('bullseye', 'em'),
  '蛇の目傍点': ('fisheye', 'em'),
  'ばつ傍点': ('saltire', 'em'),
  '傍線': ('underline_solid', 'em'),
  '二重傍線': ('underline_double', 'em'),
  '鎖線': ('underline_dotted', 'em'),
  '破線': ('underline_dashed', 'em'),
  '波線': ('underline_wave', 'em'),
  '太字': ('futoji', 'span'),
  '斜体': ('shatai', 'span'),
  '下付き小文字': ('subscript', 'sub'),
  '上付き小文字': ('superscript', 'sup'),
  '行右小書き': ('superscript', 'sup'),
  '行左小書き': ('subscript', 'sub'),
};

(String, String) decoClass(String kind, String? direction) {
  var (cls, tag) = commandTable[kind]!;
  if (direction != null) {
    if (kind.contains('点') && (direction == '左' || direction == '下')) {
      cls = '${cls}_after';
    } else if (kind.contains('線') && (direction == '左' || direction == '上')) {
      cls = cls.replaceFirst('under', 'over');
    }
  }
  return (cls, tag);
}

class AozoraParser {
  /// 面区点 → Unicode（assets/jis2ucs.json, aozora2html由来 CC0）
  final Map<String, String> jis2ucs;
  AozoraParser(this.jis2ucs);

  // ── 正規表現（parser.py と同一の意味）─────────────────────────
  static final _rubyRe = RegExp(
      r'(?:｜([^《｜]+)'
      r'|([一-鿿々-〇豈-﫿々〆ヵヶ]+))'
      r'《([^》]+)》');
  static final _gaijiNoteRe = RegExp(r'※［＃([^］]*)］');
  static final _menkutenRe = RegExp(r'([12])-(\d{1,2})-(\d{1,2})');
  static final _uplusRe = RegExp(r'[Uu]\+([0-9A-Fa-f]{4,6})');
  static final _noteRe = RegExp(r'［＃[^］]*］');

  static final String _decoKw =
      (commandTable.keys.toList()..sort((a, b) => b.length - a.length))
          .join('|');
  static final _decorateRe = RegExp(
      '(.+?)［＃「\\1」(?:の(右|左|上|下)に|に|は)($_decoKw)］');

  static const _midashiSize = {'大': 2, '中': 3, '小': 4};
  static const _midashiType = {'窓': 'mado', '同行': 'dogyo'};
  static final _headingInlineRe =
      RegExp(r'(.+?)［＃「\1」は(同行|窓)?(大|中|小)見出し］');
  static final _headingBlockRe =
      RegExp(r'［＃(同行|窓)?(大|中|小)見出し］(.*?)［＃(?:同行|窓)?\2見出し終わり］');
  static final _headingOpenRe =
      RegExp(r'^［＃(同行|窓)?(大|中|小)見出し］(.*)$');
  static final _headingCloseRe =
      RegExp(r'(.*?)［＃(?:同行|窓)?(大|中|小)見出し終わり］');

  static const _num = '[0-9０-９〇一二三四五六七八九十百]+';
  static const _layoutKw = '字下げ|字詰め|地付き|字上げ';
  static final _layoutEndRe = RegExp('［＃(?:ここで)?[^］]*?(?:$_layoutKw)終わり］');
  static final _layoutStartRe = RegExp('［＃ここから([^］]*?(?:$_layoutKw)[^］]*?)］');
  static final _layoutLineRe =
      RegExp('^［＃((?!ここから)(?!ここで)[^］]*?(?:$_layoutKw)[^］]*?)］');
  static final _jiageRe = RegExp('地から($_num)字上げ');
  static final _jizumeRe = RegExp('($_num)字詰め');
  static final _jisageRe = RegExp('($_num)字下げ');

  static final _imgRe = RegExp(
      r'［＃([^（］]*)（(fig[^、）]+\.png)(?:、横(\d+)×縦(\d+))?）入る］');

  static final _headerBlockRe = RegExp(
      '-{10,}\n【テキスト中に現れる記号について】.*?-{10,}\n',
      dotAll: true);
  static final _colophonRe = RegExp('\n(?=底本[：:])');

  // ── 外字 ──────────────────────────────────────────────
  String? _resolveNoteBody(String body) {
    if (!body.contains('非0213外字')) {
      final m = _menkutenRe.firstMatch(body);
      if (m != null) {
        final key = '${m[1]}-${m[2]!.padLeft(2, '0')}-${m[3]!.padLeft(2, '0')}';
        final ch = jis2ucs[key];
        if (ch != null) return ch;
      }
    }
    final u = _uplusRe.firstMatch(body);
    if (u != null) {
      final cp = int.tryParse(u[1]!, radix: 16);
      if (cp != null) return String.fromCharCode(cp);
    }
    return null;
  }

  String resolveGaiji(String text) => text.replaceAllMapped(
      _gaijiNoteRe, (m) => _resolveNoteBody(m[1]!) ?? geta);

  // ── 漢数字・レイアウト ──────────────────────────────────
  static const _kanjiDigit = {
    '〇': 0, '一': 1, '二': 2, '三': 3, '四': 4,
    '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
  };

  static int jpNumber(String s) {
    final t = s.trim().split('').map((c) {
      final i = '０１２３４５６７８９'.indexOf(c);
      return i >= 0 ? '$i' : c;
    }).join();
    final direct = int.tryParse(t);
    if (direct != null) return direct;
    var total = 0, cur = 0;
    for (final ch in s.trim().split('')) {
      if (_kanjiDigit.containsKey(ch)) {
        cur = _kanjiDigit[ch]!;
      } else if (ch == '十') {
        total += (cur == 0 ? 1 : cur) * 10;
        cur = 0;
      } else if (ch == '百') {
        total += (cur == 0 ? 1 : cur) * 100;
        cur = 0;
      } else {
        return 0;
      }
    }
    return total + cur;
  }

  Map<String, dynamic> _layoutFromBody(String body) {
    final jiage = _jiageRe.firstMatch(body);
    if (jiage != null) {
      return {'align': 'right', 'align_offset': jpNumber(jiage[1]!)};
    }
    if (body.contains('地付き') || body.contains('字上げ')) {
      return {'align': 'right'};
    }
    final jizume = _jizumeRe.firstMatch(body);
    if (jizume != null) return {'jizume': jpNumber(jizume[1]!)};
    final jisage = _jisageRe.firstMatch(body);
    if (jisage != null) return {'indent': jpNumber(jisage[1]!)};
    return {};
  }

  (String, Map<String, dynamic>) _applyLayout(
      String line, List<Map<String, dynamic>> stack) {
    line = line.replaceAllMapped(_layoutEndRe, (m) {
      if (stack.isNotEmpty) stack.removeLast();
      return '';
    });
    line = line.replaceAllMapped(_layoutStartRe, (m) {
      final lay = _layoutFromBody(m[1]!);
      if (lay.isNotEmpty) stack.add(lay);
      return '';
    });
    var oneline = <String, dynamic>{};
    final m = _layoutLineRe.firstMatch(line);
    if (m != null) {
      oneline = _layoutFromBody(m[1]!);
      line = line.substring(m.end);
    }
    return (line, oneline);
  }

  ({int indent, String? align, int alignOffset, int jizume}) _effectiveLayout(
      List<Map<String, dynamic>> stack, Map<String, dynamic> oneline) {
    var indent = 0, alignOffset = 0, jizume = 0;
    String? align;
    for (final l in stack) {
      indent += (l['indent'] as int?) ?? 0;
      if (l['align'] != null) {
        align = l['align'] as String;
        alignOffset = (l['align_offset'] as int?) ?? 0;
      }
      if (l['jizume'] != null) jizume = l['jizume'] as int;
    }
    indent += (oneline['indent'] as int?) ?? 0;
    if (oneline['align'] != null) {
      align = oneline['align'] as String;
      alignOffset = (oneline['align_offset'] as int?) ?? 0;
    }
    if (oneline['jizume'] != null) jizume = oneline['jizume'] as int;
    return (indent: indent, align: align, alignOffset: alignOffset, jizume: jizume);
  }

  // ── 段落 ──────────────────────────────────────────────
  List<Seg> _splitRuby(String line) {
    final segs = <Seg>[];
    var pos = 0;
    for (final m in _rubyRe.allMatches(line)) {
      if (m.start > pos) segs.add(Seg(line.substring(pos, m.start)));
      segs.add(Seg(m[1] ?? m[2]!, m[3]));
      pos = m.end;
    }
    if (pos < line.length) segs.add(Seg(line.substring(pos)));
    return segs;
  }

  Para _makePara(String line,
      {int h = 0, String? htype, String imageBase = ''}) {
    final decos = <Deco>[];
    for (final m in _decorateRe.allMatches(line)) {
      final (cls, tag) = decoClass(m[3]!, m[2]);
      decos.add(Deco(m[1]!, cls, tag));
    }
    line = line.replaceAllMapped(_decorateRe, (m) => m[1]!);

    ParaImage? image;
    final mi = _imgRe.firstMatch(line);
    if (mi != null) {
      final src = imageBase.isNotEmpty ? imageBase + mi[2]! : mi[2]!;
      image = ParaImage(src, int.tryParse(mi[3] ?? ''),
          int.tryParse(mi[4] ?? ''), mi[1] ?? '');
      line = line.replaceAll(_imgRe, '');
    }

    line = line.replaceAll(_noteRe, ''); // 未対応注記は安全に除去
    return Para(
        segs: _splitRuby(line),
        h: h,
        htype: h != 0 ? (htype ?? 'normal') : null,
        decos: decos,
        image: image);
  }

  /// 注記付きテキスト全文 → Doc
  Doc parse(String text, {String imageBase = ''}) {
    text = text.replaceAll('\r\n', '\n');
    final lines = text.split('\n');
    final title = lines.isNotEmpty ? lines[0].trim() : '';
    final author = lines.length > 1 ? lines[1].trim() : '';

    var body = lines.skip(2).join('\n');
    body = body.replaceAll(_headerBlockRe, '');
    final parts = body.split(_colophonRe);
    body = parts[0];
    final colophon = parts.length > 1 ? parts.sublist(1).join('\n').trim() : '';

    final paras = <Para>[];
    final layoutStack = <Map<String, dynamic>>[];
    ({int level, String type, List<String> parts,
      ({int indent, String? align, int alignOffset, int jizume}) layout})?
        pending;

    void addPara(Para p,
        ({int indent, String? align, int alignOffset, int jizume}) lay) {
      paras.add(Para(
          segs: p.segs,
          h: p.h,
          htype: p.htype,
          decos: p.decos,
          image: p.image,
          indent: lay.indent,
          align: lay.align,
          alignOffset: lay.alignOffset,
          jizume: lay.jizume));
    }

    for (final raw in body.split('\n')) {
      if (raw.trim().isEmpty) continue;
      var line = resolveGaiji(raw); // 外字を実文字へ（注記除去より前）

      if (pending != null) {
        final mc = _headingCloseRe.firstMatch(line);
        if (mc != null) {
          pending.parts.add(mc[1]!);
          addPara(
              _makePara(pending.parts.join(),
                  h: pending.level, htype: pending.type, imageBase: imageBase),
              pending.layout);
          pending = null;
        } else {
          pending.parts.add(line);
        }
        continue;
      }

      final (line2, oneline) = _applyLayout(line, layoutStack);
      line = line2;
      if (line.trim().isEmpty) continue;
      final layout = _effectiveLayout(layoutStack, oneline);

      final mb = _headingBlockRe.firstMatch(line);
      if (mb != null) {
        addPara(
            _makePara(mb[3]!,
                h: _midashiSize[mb[2]]!,
                htype: _midashiType[mb[1]] ?? 'normal',
                imageBase: imageBase),
            layout);
        continue;
      }

      final mo = _headingOpenRe.firstMatch(line);
      if (mo != null && !line.contains('見出し終わり')) {
        pending = (
          level: _midashiSize[mo[2]]!,
          type: _midashiType[mo[1]] ?? 'normal',
          parts: [mo[3]!],
          layout: layout
        );
        continue;
      }

      final miH = _headingInlineRe.firstMatch(line);
      if (miH != null) {
        addPara(
            _makePara(miH[1]!,
                h: _midashiSize[miH[3]]!,
                htype: _midashiType[miH[2]] ?? 'normal',
                imageBase: imageBase),
            layout);
        continue;
      }

      addPara(_makePara(line, imageBase: imageBase), layout);
    }

    return Doc(title: title, author: author, colophon: colophon, paras: paras);
  }
}
