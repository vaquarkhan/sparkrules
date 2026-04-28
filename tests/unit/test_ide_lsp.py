from __future__ import annotations

from sre.ide import analyze_drl_for_lsp


def test_lsp_analysis_ok_has_no_errors_and_completions() -> None:
    out = analyze_drl_for_lsp(
        "rule r when $t : T ( true ) then result.ok = true; end",
        prefix="ru",
    )
    assert out.diagnostics == ()
    assert "rule" in out.completions


def test_lsp_analysis_bad_drl_has_diagnostic() -> None:
    out = analyze_drl_for_lsp("broken drl {{", prefix="")
    assert out.diagnostics
    assert out.diagnostics[0].severity == "ERROR"


def test_lsp_lexer_valueerror_carries_line_col_from_message() -> None:
    out = analyze_drl_for_lsp("rule r when $t : T ( \u20ac ) then end", prefix="")
    assert out.diagnostics
    d0 = out.diagnostics[0]
    assert "at" in d0.message
    assert d0.line >= 1 and d0.col > 1
