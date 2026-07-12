import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:bunko/data/my_library.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('add persists and is visible on reload', () async {
    expect(await MyLibrary.load(), isEmpty);
    await MyLibrary.add(const AddedWork(
        url: 'https://example.com/work.json',
        title: 'テスト作品',
        author: 'テスト作者',
        addedAt: '2026-07-13T00:00:00.000'));
    final list = await MyLibrary.load();
    expect(list, hasLength(1));
    expect(list.first.title, 'テスト作品');
    expect(await MyLibrary.contains('https://example.com/work.json'), isTrue);
  });

  test('add is idempotent for the same url', () async {
    const w = AddedWork(
        url: 'https://example.com/a.json',
        title: 'A',
        author: 'X',
        addedAt: '2026-07-13T00:00:00.000');
    await MyLibrary.add(w);
    await MyLibrary.add(w);
    expect(await MyLibrary.load(), hasLength(1));
  });

  test('remove drops the entry', () async {
    await MyLibrary.add(const AddedWork(
        url: 'https://example.com/b.json',
        title: 'B',
        author: 'Y',
        addedAt: '2026-07-13T00:00:00.000'));
    expect(await MyLibrary.contains('https://example.com/b.json'), isTrue);
    await MyLibrary.remove('https://example.com/b.json');
    expect(await MyLibrary.contains('https://example.com/b.json'), isFalse);
    expect(await MyLibrary.load(), isEmpty);
  });

  test('saveBody/loadBody round-trips a downloaded copy', () async {
    const url = 'https://example.com/c.json';
    expect(await MyLibrary.hasBody(url), isFalse);
    await MyLibrary.saveBody(url, '{"title":"手元保存版"}');
    expect(await MyLibrary.hasBody(url), isTrue);
    expect(await MyLibrary.loadBody(url), '{"title":"手元保存版"}');
  });

  test('clearBody removes the downloaded copy', () async {
    const url = 'https://example.com/d.json';
    await MyLibrary.saveBody(url, '{"title":"x"}');
    await MyLibrary.clearBody(url);
    expect(await MyLibrary.hasBody(url), isFalse);
    expect(await MyLibrary.loadBody(url), isNull);
  });

  test('remove() also clears any downloaded body for that url', () async {
    const url = 'https://example.com/e.json';
    await MyLibrary.add(const AddedWork(
        url: url, title: 'E', author: 'Z', addedAt: '2026-07-13T00:00:00.000'));
    await MyLibrary.saveBody(url, '{"title":"E"}');
    await MyLibrary.remove(url);
    expect(await MyLibrary.hasBody(url), isFalse);
  });
}
