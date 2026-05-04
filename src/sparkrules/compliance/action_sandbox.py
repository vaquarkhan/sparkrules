from __future__ import annotations

import ast

_DISALLOWED = (
    ast.Call,
    ast.Attribute,
    ast.Lambda,
    ast.NamedExpr,
    ast.Await,
    ast.Yield,
    ast.YieldFrom,
)


def validate_python_literal_expression(src: str) -> None:
    """Reject obvious non-literal Python snippets (calls, attribute access, lambdas)."""

    tree = ast.parse((src or "").strip() or "0", mode="eval")
    for node in ast.walk(tree):
        if isinstance(node, _DISALLOWED):
            msg = f"disallowed expression node: {type(node).__name__}"
            raise ValueError(msg)
