"""Editor-style DRL diagnostics without running an LSP server.

Uses :func:`sparkrules.ide.analyze_drl_for_lsp` (parse errors + keyword completions).

  python examples/python/lsp_analyze_drl_demo.py
"""

from __future__ import annotations

from sparkrules.ide import analyze_drl_for_lsp


def main() -> None:
    ok = analyze_drl_for_lsp('rule "ok" when $t : T ( true ) then end')
    print("valid rule diagnostics:", len(ok.diagnostics), "completions sample:", ok.completions[:8])

    bad = analyze_drl_for_lsp('rule "bad" when $t : T ( true ) then oops')
    for d in bad.diagnostics:
        print(f"ERROR L{d.line}:C{d.col}: {d.message}")


if __name__ == "__main__":
    main()
