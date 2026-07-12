"""kosei.py（機械チェック・作業履歴）のテスト。作業マニュアルの例で検証する。"""
from pybunko.kosei import charset_errors, lint, work_history


def _rules(findings):
    return {f.rule for f in findings}


def test_charset_jisx0208_gai():
    # 「靑」はJIS X 0208に無い（包摂適用で「青」にすべき）。①は機種依存文字。
    fs = charset_errors('靑空文庫\n①番\n')
    assert len(fs) == 2
    assert fs[0].line == 1 and '靑' in fs[0].note
    assert fs[1].line == 2 and '①' in fs[1].note


def test_charset_hankaku_kana_and_ok_text():
    fs = charset_errors('ｱｵｿﾞﾗ\n')
    assert fs and '半角カナ' in fs[0].note
    assert charset_errors('走れメロス《めろす》。［＃改ページ］\n') == []


def test_lint_hepebe_confusion():
    # 片仮名列に接する平仮名「へ」（誤読の頻出形）
    fs = lint('ページの上へ、ソヴィエトべったり\n')
    assert 'へぺべの混同疑い' in _rules(fs)


def test_lint_ruby_rules():
    fs = lint('長い漢字四文字《よみ》と火照《ほて》つた\n')
    assert '｜の入れ忘れ疑い' in _rules(fs)
    fs = lint('学校《gakkou》\n')
    assert 'ルビに仮名以外' in _rules(fs)
    fs = lint('教室《きようしつ》\n')
    assert 'ルビ拗音の並字疑い' in _rules(fs)
    assert lint('老爺《ろうや》と磔《はりつけ》\n') == []  # 正当な並字は拾わない


def test_lint_indent_and_trailing():
    fs = lint('　「行頭括弧の前は字下げしない」\nこの行は文末に空白　\n')
    assert '行頭括弧前の字下げ' in _rules(fs)
    assert '文末の空白' in _rules(fs)


def test_lint_ocr_list():
    # 校正編のOCR頻出リストから: 「意昧」ではなく単独語の例「間題」「咋日」
    fs = lint('その間題は咋日のことだ。\n')
    hits = [f for f in fs if f.rule == 'OCR誤読疑い']
    assert len(hits) == 2
    assert '間題' in hits[0].note and '咋日' in hits[1].note


def test_lint_old_style_shinji():
    fs = lint('學問の獨立と学問\n', old_style=True)
    assert '新字の混入疑い' in _rules(fs)
    # 新字モード（既定）では出ない
    assert '新字の混入疑い' not in _rules(lint('学問\n'))


def test_lint_clean_text_is_quiet():
    clean = '　メロスは激怒した。必ず、かの邪智暴虐《じゃちぼうぎゃく》の王を除かなければならぬと決意した。\n'
    assert lint(clean) == []


def test_work_history_manual_example():
    # 校正編の例そのまま: 意昧→意味 で【昧】が付く
    before = '第一章\n意昧のない抵抗を\nそのまま\n'
    after = '第一章\n意味のない抵抗を\nそのまま\n'
    h = work_history(before, after)
    assert '意昧のない抵抗を　→　意味のない抵抗を　【昧】' in h


def test_work_history_window_and_empty():
    # 長い行は差分の周辺だけ抜粋される
    before = 'あ' * 30 + '鳴呼' + 'い' * 30
    after = 'あ' * 30 + '嗚呼' + 'い' * 30
    h = work_history(before, after)
    assert '【鳴】' in h and '…' in h and len(h) < 60
    assert work_history('同じ\n', '同じ\n') == '修正点はありませんでした。\n'
