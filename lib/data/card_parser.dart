/// 図書カード（cardNNNN.html）→ 構造化 dict。
///
/// Python 側 aozorabunko/card.py の Dart 移植（work/authors/books/staff/files）。
/// カードのメタデータは CC BY 4.0。ミラー上は UTF-8。
library;

final _trRe = RegExp(r'<tr[^>]*>(.*?)</tr>', dotAll: true);
final _cellRe = RegExp(r'<t[hd][^>]*>(.*?)</t[hd]>', dotAll: true);
final _tagRe = RegExp(r'<[^>]+>');
final _h2Re = RegExp(r'<h2[^>]*>(.*?)</h2>', dotAll: true);

String _strip(String cell) =>
    cell.replaceAll(_tagRe, '').replaceAll('&nbsp;', ' ').trim();

List<List<String>> _rows(String html) {
  final out = <List<String>>[];
  for (final tr in _trRe.allMatches(html)) {
    final cells = [
      for (final c in _cellRe.allMatches(tr[1]!))
        _strip(c[1]!).replaceAll(RegExp(r'[：:]+$'), '')
    ];
    if (cells.any((c) => c.isNotEmpty)) out.add(cells);
  }
  return out;
}

List<(String, String)> _pairs(List<List<String>> rows) => [
      for (final r in rows)
        if (r.length >= 2 && r[0].isNotEmpty) (r[0], r[1])
    ];

Map<String, dynamic> parseCard(String html) {
  final marks = [
    for (final m in _h2Re.allMatches(html)) (m.start, _strip(m[1]!))
  ];
  final sections = <String, String>{};
  for (var i = 0; i < marks.length; i++) {
    final end = i + 1 < marks.length ? marks[i + 1].$1 : html.length;
    sections[marks[i].$2] = html.substring(marks[i].$1, end);
  }

  final card = <String, dynamic>{};
  // カード冒頭（最初のh2より前）のタイトル表: 作品名・著者名など
  final head = marks.isEmpty ? html : html.substring(0, marks.first.$1);
  final work = <String, String>{for (final (k, v) in _pairs(_rows(head))) k: v};
  if (sections.containsKey('作品データ')) {
    for (final (k, v) in _pairs(_rows(sections['作品データ']!))) {
      work[k] = v;
    }
  }
  card['work'] = work;

  if (sections.containsKey('作家データ')) {
    final authors = <Map<String, String>>[];
    for (final (k, v) in _pairs(_rows(sections['作家データ']!))) {
      if (k == '分類') {
        authors.add({'分類': v});
      } else if (authors.isNotEmpty) {
        authors.last[k] = v;
      }
    }
    card['authors'] = authors;
  }

  if (sections.containsKey('底本データ')) {
    final books = <Map<String, String>>[];
    for (final (k, v) in _pairs(_rows(sections['底本データ']!))) {
      if (k == '底本' || k == '底本の親本') {
        books.add({'role': k, '名称': v});
      } else if (books.isNotEmpty) {
        books.last[k] = v;
      }
    }
    card['books'] = books;
  }

  if (sections.containsKey('工作員データ')) {
    card['staff'] = {
      for (final (k, v) in _pairs(_rows(sections['工作員データ']!))) k: v
    };
  }
  return card;
}
