from __future__ import annotations

import re
from dataclasses import dataclass

from sparkrules.parser import parse
from sparkrules.parser.ast import ParseError
from sparkrules.parser.lexer import _KEYWORDS


@dataclass(frozen=True, slots=True)
class LspDiagnostic:
    severity: str
    message: str
    line: int
    col: int


@dataclass(frozen=True, slots=True)
class LspAnalysis:
    diagnostics: tuple[LspDiagnostic, ...]
    completions: tuple[str, ...]


_MSG_AT_LOC = re.compile(r" at (\d+):(\d+)\s*$")


def _line_col_from_message(msg: str) -> tuple[int, int]:
    m = _MSG_AT_LOC.search(msg)
    if m:
        return max(1, int(m.group(1))), max(1, int(m.group(2)))
    return 1, 1


_COMMON_SNIPPETS: tuple[str, ...] = (
    "rule",
    "when",
    "then",
    "end",
    "salience",
    "agenda_group",
    "activation_group",
    "stop_on_fire",
    "result.",
)


def _completion_pool() -> tuple[str, ...]:
    return tuple(sorted(set(_COMMON_SNIPPETS) | set(_KEYWORDS.keys())))


def analyze_drl_for_lsp(drl: str, *, prefix: str = "") -> LspAnalysis:
    diags: list[LspDiagnostic] = []
    try:
        parse(drl)
    except ParseError as e:
        diags.append(
            LspDiagnostic(
                severity="ERROR",
                message=str(e),
                line=max(1, int(e.line or 1)),
                col=max(1, int(e.col or 1)),
            )
        )
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        ln, col = _line_col_from_message(msg)
        diags.append(
            LspDiagnostic(
                severity="ERROR",
                message=msg,
                line=ln,
                col=col,
            )
        )
    pool = _completion_pool()
    p = prefix.strip().lower()
    if not p:
        comps = pool
    else:
        comps = tuple(x for x in pool if x.lower().startswith(p))
    return LspAnalysis(diagnostics=tuple(diags), completions=comps)
