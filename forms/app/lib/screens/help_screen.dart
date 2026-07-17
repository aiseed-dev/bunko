import 'package:flutter/material.dart';

class HelpScreen extends StatelessWidget {
  const HelpScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('このアプリについて')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: const [
          _Paragraph(
            'FormRescue は、WordPressの問い合わせフォームに届いたデータを、'
            'Cloudflare上の受信箱から自分の端末に引き取り、手元で確認・管理する'
            'ためのアプリです。データを溜める場所をWordPressから切り離すことで、'
            'サイトが攻撃されても顧客データを失わない状態を作ります。',
          ),
          _SectionTitle('データの流れ'),
          _Paragraph(
            '1. 訪問者がサイトの問い合わせフォームから送信する\n'
            '2. データはWordPressには残らず、Cloudflareの受信箱に一時保存される\n'
            '3. このアプリが受信箱から取得し、この端末の中に保存する\n'
            '4. 内容を読んで「確認」すると、受信箱側のデータは削除される',
          ),
          _Paragraph(
            '受信箱からの削除は「確認」操作だけです。自動削除はありません。',
          ),
          _SectionTitle('取得のタイミング'),
          _Paragraph(
            'アプリ起動時、右上の「取得」ボタン、およびアプリを開いている間は'
            '数時間おきに自動で取得します。',
          ),
          _SectionTitle('「確認」と「対応済み」'),
          _Paragraph(
            '確認: 内容を読んだ、という印。受信箱から削除され、データはこの端末'
            'だけに残ります。\n'
            '対応済み: 返信などの対応を終えた、という印。端末内の整理用です。',
          ),
          _SectionTitle('設定に必要なもの'),
          _Paragraph(
            'Worker URL と PULL_TOKEN の二つ。どちらも受信箱を設置したとき'
            '(deploy.py または cf-publish の実行時)に表示されます。'
            'QRコードを読み取れば手入力は不要です(Android/iOS版)。',
          ),
          _SectionTitle('データの保存場所'),
          _Paragraph(
            '取得したデータは、この端末の中のアプリ専用データベース(SQLite)に'
            'だけ保存されます。クラウドには置かれません。起動時に1日1回バック'
            'アップを作成し、直近30日分を保持します。',
          ),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String text;
  const _SectionTitle(this.text);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 20, bottom: 8),
      child: Text(text, style: Theme.of(context).textTheme.titleMedium),
    );
  }
}

class _Paragraph extends StatelessWidget {
  final String text;
  const _Paragraph(this.text);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(text),
    );
  }
}
