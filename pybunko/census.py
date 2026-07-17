"""census.py — コーパス一括点検（未対応注記・未解決外字の国勢調査）。

「どの注記から対応すべきか」を勘でなくデータで決めるための道具。
作品を横断して parse(unknown_notes=) の報告を集計し、正規化した
注記パターンごとの頻度・出現作品数を出す。

正規化: 「…」の中身と数値を畳む（［＃ここから７字下げ］→［＃ここからN字下げ］）
ので、書式パターン単位で数えられる。

    python -m pybunko.census --limit 300 -o report.json
"""
from __future__ import annotations

import json
import re
from collections import Counter

from .catalog import Library
from .gaiji import resolve_note_body
from .parser import parse

_QUOTE_RE = re.compile(r'「[^「」]*」')
_NUM_RE = re.compile(r'[0-9０-９一二三四五六七八九十]+')
_GAIJI_NOTE_RE = re.compile(r'※［＃([^］]*)］')


def normalize_note(body: str) -> str:
    """注記本文を書式パターンに畳む。"""
    s = _QUOTE_RE.sub('「…」', body)
    s = _NUM_RE.sub('N', s)
    return s


def census(works=None, library: Library | None = None,
           limit: int = 300, progress=None) -> dict:
    """作品を巡回して未対応注記・未解決外字を集計する。

    works を省略すると Library の全カタログから、作家が偏らないよう
    等間隔に limit 作品を選ぶ。返り値:
      {'scanned': n, 'errors': n,
       'unknown': [{'pattern', 'count', 'works', 'example'}, ...],
       'gaiji_unresolved': [{'pattern', 'count', 'example'}, ...]}
    """
    if works is None:
        all_works = (library or Library()).works
        step = max(1, len(all_works) // limit)
        works = all_works[::step][:limit]
    pat_count: Counter = Counter()
    pat_works: dict[str, set] = {}
    pat_example: dict[str, str] = {}
    gai_count: Counter = Counter()
    gai_example: dict[str, str] = {}
    scanned = errors = 0
    for k, w in enumerate(works):
        try:
            text = w.text()
        except Exception:
            errors += 1
            continue
        scanned += 1
        unknown: list[str] = []
        parse(text, unknown_notes=unknown)
        for body in unknown:
            p = normalize_note(body)
            pat_count[p] += 1
            pat_works.setdefault(p, set()).add(w.work_id)
            pat_example.setdefault(p, f'［＃{body}］ ── {w.title}')
        for body in _GAIJI_NOTE_RE.findall(text):
            if resolve_note_body(body) is None:
                p = normalize_note(body)
                gai_count[p] += 1
                gai_example.setdefault(p, f'※［＃{body}］ ── {w.title}')
        if progress:
            progress(k + 1, len(works))
    return {
        'scanned': scanned,
        'errors': errors,
        'unknown': [
            {'pattern': p, 'count': n, 'works': len(pat_works[p]),
             'example': pat_example[p]}
            for p, n in pat_count.most_common()],
        'gaiji_unresolved': [
            {'pattern': p, 'count': n, 'example': gai_example[p]}
            for p, n in gai_count.most_common()],
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        prog='python -m pybunko.census',
        description='コーパス一括点検（未対応注記・未解決外字の頻度統計）')
    ap.add_argument('--limit', type=int, default=300, help='走査する作品数')
    ap.add_argument('-o', '--out', help='レポートJSONの出力先')
    ap.add_argument('--top', type=int, default=30, help='表示する上位件数')
    a = ap.parse_args(argv)

    rep = census(limit=a.limit,
                 progress=lambda d, t: print(f'\r{d}/{t}', end='', flush=True))
    print(f"\n走査 {rep['scanned']} 作品（取得失敗 {rep['errors']}）")
    print(f"\n== 未対応注記 上位{a.top}（パターン数 {len(rep['unknown'])}）")
    for e in rep['unknown'][:a.top]:
        print(f"  {e['count']:5d}回 / {e['works']:3d}作品  ［＃{e['pattern']}］")
        print(f"         例: {e['example'][:70]}")
    print(f"\n== 未解決外字 上位10（パターン数 {len(rep['gaiji_unresolved'])}）")
    for e in rep['gaiji_unresolved'][:10]:
        print(f"  {e['count']:5d}回  {e['example'][:70]}")
    if a.out:
        from pathlib import Path
        Path(a.out).write_text(json.dumps(rep, ensure_ascii=False, indent=1),
                               encoding='utf-8')
        print(f'\nレポート: {a.out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
