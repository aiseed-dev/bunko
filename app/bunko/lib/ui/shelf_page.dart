/// 書架（ホーム） —— 青空文庫の「総合インデックス」の作法に合わせる。
///
/// 公式サイトと同じ2軸: **作家別** と **作品別**。五十音の行（あ〜わ・その他）を選ぶと、
/// 公式同様に行内の**個別のかな**（あ行→ア・イ・ウ・エ・オ）でさらに絞れる。
/// 濁音・半濁音は清音に含める（公式の分類に準拠: カにガ、ハにバ・パ）。
library;

import 'package:flutter/material.dart';

import '../data/db.dart';
import '../data/fetch.dart';
import '../data/models.dart';
import '../theme.dart';
import 'card_page.dart';

const kanaRows = ['あ', 'か', 'さ', 'た', 'な', 'は', 'ま', 'や', 'ら', 'わ', 'その他'];

/// 行 → 個別かな（表示はカタカナ=公式流、値は清音＋濁半濁のよみ頭文字群）
const Map<String, List<(String, List<String>)>> kanaOfRow = {
  'あ': [('ア', ['あ']), ('イ', ['い']), ('ウ', ['う', 'ゔ']), ('エ', ['え']), ('オ', ['お'])],
  'か': [('カ', ['か', 'が']), ('キ', ['き', 'ぎ']), ('ク', ['く', 'ぐ']),
        ('ケ', ['け', 'げ']), ('コ', ['こ', 'ご'])],
  'さ': [('サ', ['さ', 'ざ']), ('シ', ['し', 'じ']), ('ス', ['す', 'ず']),
        ('セ', ['せ', 'ぜ']), ('ソ', ['そ', 'ぞ'])],
  'た': [('タ', ['た', 'だ']), ('チ', ['ち', 'ぢ']), ('ツ', ['つ', 'づ', 'っ']),
        ('テ', ['て', 'で']), ('ト', ['と', 'ど'])],
  'な': [('ナ', ['な']), ('ニ', ['に']), ('ヌ', ['ぬ']), ('ネ', ['ね']), ('ノ', ['の'])],
  'は': [('ハ', ['は', 'ば', 'ぱ']), ('ヒ', ['ひ', 'び', 'ぴ']), ('フ', ['ふ', 'ぶ', 'ぷ']),
        ('ヘ', ['へ', 'べ', 'ぺ']), ('ホ', ['ほ', 'ぼ', 'ぽ'])],
  'ま': [('マ', ['ま']), ('ミ', ['み']), ('ム', ['む']), ('メ', ['め']), ('モ', ['も'])],
  'や': [('ヤ', ['や', 'ゃ']), ('ユ', ['ゆ', 'ゅ']), ('ヨ', ['よ', 'ょ'])],
  'ら': [('ラ', ['ら']), ('リ', ['り']), ('ル', ['る']), ('レ', ['れ']), ('ロ', ['ろ'])],
  'わ': [('ワ', ['わ']), ('ヰ', ['ゐ']), ('ヱ', ['ゑ']), ('ヲ', ['を']), ('ン', ['ん'])],
};

/// NDC最上位（類）のラベル（公式「分野別リスト」準拠。K=児童書）
const Map<String, String> ndcTopLabels = {
  '0': '総記', '1': '哲学', '2': '歴史', '3': '社会科学', '4': '自然科学',
  '5': '技術', '6': '産業', '7': '芸術', '8': '言語', '9': '文学', 'K': '児童書',
};

/// よく現れる3桁分類のラベル（無いものはコードのみ表示）
const Map<String, String> ndcSubLabels = {
  '121': '日本思想', '159': '人生訓', '210': '日本史', '280': '伝記', '289': '個人伝記',
  '291': '日本地誌', '304': '社会評論', '361': '社会学', '370': '教育', '388': '伝説・民話',
  '410': '数学', '420': '物理学', '440': '天文', '460': '生物', '480': '動物', '490': '医学',
  '498': '衛生', '520': '建築', '588': '食品工業', '596': '料理', '610': '農業',
  '620': '園芸', '660': '水産', '699': '放送', '720': '絵画', '740': '写真', '760': '音楽',
  '770': '演劇', '775': '演劇史', '778': '映画', '780': 'スポーツ', '790': '諸芸・娯楽',
  '800': '言語', '810': '日本語', '830': '英語', '900': '文学（総記）',
  '901': '文学論', '902': '文学史', '908': '全集', '910': '日本文学（評論）',
  '911': '詩歌', '912': '戯曲', '913': '小説・物語', '914': '評論・随筆',
  '915': '日記・紀行', '916': '記録・手記', '917': '箴言', '918': '作品集', '919': '漢詩文',
  '920': '中国文学', '923': '中国小説', '929': '東洋文学', '930': '英米文学（評論）',
  '933': '英米小説', '934': '英米評論', '935': '英米日記', '940': 'ドイツ文学',
  '943': 'ドイツ小説', '950': 'フランス文学', '953': 'フランス小説', '954': '仏評論',
  '960': 'スペイン文学', '963': 'スペイン小説', '970': 'イタリア文学', '973': '伊小説',
  '980': 'ロシア文学', '983': 'ロシア小説', '989': '他スラブ文学', '990': '他言語文学',
};

String ndcSubLabel(String code) {
  final digits = code.startsWith('K') ? code.substring(1) : code;
  final label = ndcSubLabels[digits];
  return label == null ? code : '$code $label';
}

enum ShelfMode { author, title, ndc } // 作家別 / 作品別 / 分野別（公式の3軸）

class ShelfPage extends StatefulWidget {
  final BunkoDb db;
  final Fetcher fetcher;
  const ShelfPage({super.key, required this.db, required this.fetcher});

  @override
  State<ShelfPage> createState() => _ShelfPageState();
}

class _ShelfPageState extends State<ShelfPage> {
  ShelfMode _mode = ShelfMode.author;
  String _row = 'あ';
  (String, List<String>)? _kana; // 選択中の個別かな（null=行全体）
  String _ndcTop = '9'; // 分野別: 選択中の類（文学が既定）
  String? _ndcSub; // 分野別: 選択中の3桁分類（null=類全体）
  String _query = '';

  void _setRow(String row) => setState(() {
        _row = row;
        _kana = null;
      });

  @override
  Widget build(BuildContext context) {
    final st = widget.db.stats();
    final modeLabel = switch (_mode) {
      ShelfMode.author => '作家別作品一覧',
      ShelfMode.title => '作品別一覧',
      ShelfMode.ndc => '分野別リスト',
    };
    return Scaffold(
      appBar: AppBar(
        titleSpacing: 20,
        title: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('文庫',
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.w600)),
          Text('青空文庫　公開中　$modeLabel ── ${st.authors} 作家 ／ ${st.works} 作品',
              style: const TextStyle(fontSize: 11, color: Sumi.muted)),
        ]),
        toolbarHeight: 64,
      ),
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 6),
          child: Row(children: [
            Expanded(
              child: TextField(
                decoration: const InputDecoration(
                    hintText: '作品名・作家名・よみ で検索',
                    prefixIcon: Icon(Icons.search, color: Sumi.muted)),
                onChanged: (v) => setState(() => _query = v.trim()),
              ),
            ),
            const SizedBox(width: 10),
            // 公式の2軸: 作家別 / 作品別
            SegmentedButton<ShelfMode>(
              segments: const [
                ButtonSegment(value: ShelfMode.author, label: Text('作家別')),
                ButtonSegment(value: ShelfMode.title, label: Text('作品別')),
                ButtonSegment(value: ShelfMode.ndc, label: Text('分野別')),
              ],
              selected: {_mode},
              showSelectedIcon: false,
              style: ButtonStyle(
                visualDensity: VisualDensity.compact,
                foregroundColor: WidgetStateProperty.resolveWith((s) =>
                    s.contains(WidgetState.selected)
                        ? Sumi.paperHi
                        : Sumi.inkSoft),
                backgroundColor: WidgetStateProperty.resolveWith((s) =>
                    s.contains(WidgetState.selected) ? Sumi.shu : Sumi.paperHi),
              ),
              onSelectionChanged: (s) => setState(() {
                _mode = s.first;
                _kana = null;
                _ndcSub = null;
              }),
            ),
          ]),
        ),
        if (_query.isEmpty && _mode == ShelfMode.ndc) ...[
          // 分野（NDC類。公式: 分野別リスト）
          SizedBox(
            height: 44,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              children: [
                for (final t in widget.db.ndcTop())
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 3),
                    child: ChoiceChip(
                      label: Text(
                          '${ndcTopLabels[t.$1] ?? t.$1}（${t.$2}）'),
                      selected: _ndcTop == t.$1,
                      selectedColor: Sumi.shu,
                      labelStyle: TextStyle(
                          fontSize: 12,
                          color:
                              _ndcTop == t.$1 ? Sumi.paperHi : Sumi.inkSoft),
                      onSelected: (_) => setState(() {
                        _ndcTop = t.$1;
                        _ndcSub = null;
                      }),
                    ),
                  ),
              ],
            ),
          ),
          // 類内の3桁分類
          SizedBox(
            height: 40,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              children: [
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 3),
                  child: ChoiceChip(
                    label: const Text('すべて'),
                    selected: _ndcSub == null,
                    selectedColor: Sumi.inkSoft,
                    labelStyle: TextStyle(
                        fontSize: 12,
                        color: _ndcSub == null ? Sumi.paperHi : Sumi.muted),
                    onSelected: (_) => setState(() => _ndcSub = null),
                  ),
                ),
                for (final c in widget.db.ndcSub(_ndcTop))
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 3),
                    child: ChoiceChip(
                      label: Text('${ndcSubLabel(c.$1)}（${c.$2}）'),
                      selected: _ndcSub == c.$1,
                      selectedColor: Sumi.shu,
                      labelStyle: TextStyle(
                          fontSize: 12,
                          color:
                              _ndcSub == c.$1 ? Sumi.paperHi : Sumi.inkSoft),
                      onSelected: (_) => setState(() => _ndcSub = c.$1),
                    ),
                  ),
              ],
            ),
          ),
        ],
        if (_query.isEmpty && _mode != ShelfMode.ndc) ...[
          // 五十音の行（公式: あ行〜わ行）
          SizedBox(
            height: 44,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              children: [
                for (final r in kanaRows)
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 3),
                    child: ChoiceChip(
                      label: Text(r == 'その他' ? r : '$r行'),
                      selected: _row == r,
                      selectedColor: Sumi.shu,
                      labelStyle: TextStyle(
                          color: _row == r ? Sumi.paperHi : Sumi.inkSoft),
                      onSelected: (_) => _setRow(r),
                    ),
                  ),
              ],
            ),
          ),
          // 行内の個別かな（公式: あ行 → ア イ ウ エ オ）
          if (kanaOfRow.containsKey(_row))
            SizedBox(
              height: 40,
              child: ListView(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 12),
                children: [
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 3),
                    child: ChoiceChip(
                      label: const Text('すべて'),
                      selected: _kana == null,
                      selectedColor: Sumi.inkSoft,
                      labelStyle: TextStyle(
                          fontSize: 12,
                          color: _kana == null ? Sumi.paperHi : Sumi.muted),
                      onSelected: (_) => setState(() => _kana = null),
                    ),
                  ),
                  for (final k in kanaOfRow[_row]!)
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 3),
                      child: ChoiceChip(
                        label: Text(k.$1),
                        selected: _kana?.$1 == k.$1,
                        selectedColor: Sumi.shu,
                        labelStyle: TextStyle(
                            fontSize: 12,
                            color: _kana?.$1 == k.$1
                                ? Sumi.paperHi
                                : Sumi.inkSoft),
                        onSelected: (_) => setState(() => _kana = k),
                      ),
                    ),
                ],
              ),
            ),
        ],
        const Divider(height: 8),
        Expanded(
          child: _query.isNotEmpty
              ? _searchList()
              : switch (_mode) {
                  ShelfMode.author => _authorList(),
                  ShelfMode.title => _titleList(),
                  ShelfMode.ndc => _ndcList(),
                },
        ),
      ]),
    );
  }

  Widget _searchList() {
    final hits = widget.db.search(_query);
    if (hits.isEmpty) {
      return const Center(
          child: Text('見つかりませんでした', style: TextStyle(color: Sumi.muted)));
    }
    return ListView.separated(
      itemCount: hits.length,
      separatorBuilder: (c, i) => const Divider(height: 1),
      itemBuilder: (context, i) => _workTile(hits[i]),
    );
  }

  // ── 作家別（公式: 公開中 作家別作品一覧） ─────────────────────
  Widget _authorList() {
    final authors = widget.db.authors(row: _row, initials: _kana?.$2);
    if (authors.isEmpty) {
      return const Center(
          child: Text('該当する作家がいません', style: TextStyle(color: Sumi.muted)));
    }
    return ListView.builder(
      itemCount: authors.length,
      itemBuilder: (context, i) {
        final a = authors[i];
        return ExpansionTile(
          shape: const Border(),
          title: Row(children: [
            Flexible(
                child: Text(a.author,
                    style: const TextStyle(fontWeight: FontWeight.w600))),
            const SizedBox(width: 8),
            Text(a.authorYomi,
                style: const TextStyle(fontSize: 11, color: Sumi.muted)),
          ]),
          trailing: Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
            decoration: BoxDecoration(
                color: Sumi.shu.withValues(alpha: .1),
                borderRadius: BorderRadius.circular(999)),
            child: Text('${a.count}',
                style: const TextStyle(color: Sumi.shu, fontSize: 12)),
          ),
          children: [
            for (final w in widget.db.byAuthor(a.author, a.authorYomi))
              _workTile(w, dense: true),
          ],
        );
      },
    );
  }

  // ── 作品別（公式: 公開中 作品別一覧） ────────────────────────
  Widget _titleList() {
    final initials = _kana?.$2 ??
        kanaOfRow[_row]?.expand((k) => k.$2).toList() ??
        const <String>[];
    if (initials.isEmpty) {
      return const Center(
          child: Text('「その他」は作家別でご覧ください',
              style: TextStyle(color: Sumi.muted)));
    }
    final works = widget.db.worksByTitleKana(initials);
    if (works.isEmpty) {
      return const Center(
          child: Text('該当する作品がありません', style: TextStyle(color: Sumi.muted)));
    }
    return ListView.separated(
      itemCount: works.length,
      separatorBuilder: (c, i) => const Divider(height: 1),
      itemBuilder: (context, i) => _workTile(works[i]),
    );
  }

  // ── 分野別（公式: 分野別リスト＝NDC分類） ────────────────────
  Widget _ndcList() {
    final works = widget.db.worksByNdc(_ndcSub ?? _ndcTop);
    if (works.isEmpty) {
      return const Center(
          child: Text('該当する作品がありません', style: TextStyle(color: Sumi.muted)));
    }
    return ListView.separated(
      itemCount: works.length,
      separatorBuilder: (c, i) => const Divider(height: 1),
      itemBuilder: (context, i) => _workTile(works[i], showNdc: true),
    );
  }

  Widget _workTile(WorkMeta w, {bool dense = false, bool showNdc = false}) {
    return ListTile(
      dense: dense,
      contentPadding: EdgeInsets.only(left: dense ? 32 : 16, right: 16),
      title: Text(w.title),
      subtitle: dense
          ? null
          : Text(
              '${w.author}　${w.titleYomi}'
              '${showNdc && w.ndc.isNotEmpty ? '　NDC ${w.ndc}' : ''}',
              style: const TextStyle(fontSize: 12, color: Sumi.muted)),
      trailing: Row(mainAxisSize: MainAxisSize.min, children: [
        if (w.readingCorpus)
          const Tooltip(
              message: '読みデータあり（NDL朗読コーパス）',
              child:
                  Icon(Icons.record_voice_over, size: 16, color: Sumi.muted)),
        if (w.hasDoc) ...[
          const SizedBox(width: 6),
          const Icon(Icons.download_done, size: 16, color: Sumi.muted),
        ],
      ]),
      onTap: () => Navigator.of(context).push(MaterialPageRoute(
          builder: (_) =>
              CardPage(work: w, db: widget.db, fetcher: widget.fetcher))),
    );
  }
}
