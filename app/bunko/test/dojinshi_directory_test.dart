import 'package:flutter_test/flutter_test.dart';

import 'package:bunko/data/dojinshi_directory.dart';

void main() {
  test('parses entries and drops ones without a url', () {
    final list = parseDirectory('''
      [
        {"title": "テスト作品", "author": "テスト作者",
         "url": "https://example.com/a.json", "blurb": "紹介文"},
        {"title": "URL無し", "author": "誰か"}
      ]
    ''');
    expect(list, hasLength(1));
    expect(list.first.title, 'テスト作品');
    expect(list.first.url, 'https://example.com/a.json');
  });

  test('empty directory parses to an empty list', () {
    expect(parseDirectory('[]'), isEmpty);
  });
}
