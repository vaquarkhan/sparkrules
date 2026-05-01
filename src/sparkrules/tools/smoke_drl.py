"""Parse and pretty-print a minimal DRL sample.

Use this instead of one-line ``python -c`` on Windows PowerShell, which often
mangles ``$`` in quoted strings. Run after ``pip install -e ".[test]"``::

  python -m sre.tools.smoke_drl
"""

from __future__ import annotations

import sys

from sparkrules.parser import parse, print_ast

_SAMPLE = r"""
rule r1
when
$t : T ( $t.x == 1 )
then
result.x = 1;
end
"""


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = list(sys.argv[1:])
    source = _SAMPLE
    if len(argv) >= 1:
        path = argv[0]
        source = _read_text(path)
    r = parse(source)
    sys.stdout.write(print_ast(r))
    return 0


def _read_text(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    raise SystemExit(main())
