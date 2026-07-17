"""python -m pybunko ── Shift_JIS 注記付きテキスト → Unicode JSON。"""
import argparse
import sys

from .convert import to_json


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog='pybunko',
        description='青空文庫の注記付きテキスト(Shift_JIS)をUnicode構造化JSONに変換する')
    ap.add_argument('input', help='注記付きテキスト（.txt / .zip / URL）')
    ap.add_argument('-o', '--output', help='出力JSONパス（省略時は標準出力）')
    ap.add_argument('--indent', type=int, default=None,
                    help='JSONのインデント（省略時は1行）')
    ap.add_argument('--image-base', default='',
                    help='挿絵srcを解決するベースURL')
    a = ap.parse_args(argv)
    js = to_json(a.input, a.output, indent=a.indent, image_base=a.image_base)
    if not a.output:
        sys.stdout.write(js + '\n')
    else:
        sys.stderr.write(f'wrote {a.output}: {len(js.encode("utf-8")):,} bytes\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
