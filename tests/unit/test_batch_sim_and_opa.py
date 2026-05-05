"""Tests for batch simulation endpoint and OPA/Rego export."""

from __future__ import annotations

from fastapi.testclient import TestClient

from sparkrules.api import AppDeps, create_app
from sparkrules.export.opa import export_to_rego, _expr_to_rego, _rule_to_rego
from sparkrules.parser import parse
from sparkrules.parser.ast import Literal, Not, InExpr, ListExpr, CallExpr


# --- Batch simulation ---


def test_batch_simulation_multiple_facts() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    drl = "rule r when $t : T ( $t.x > 5 ) then result.v = 1; end"
    r = c.post(
        "/simulations/batch",
        json={
            "drl": drl,
            "facts": [
                {"t": {"x": 10}},
                {"t": {"x": 3}},
                {"t": {"x": 8}},
            ],
        },
    )
    assert r.status_code == 200
    j = r.json()
    assert j["total"] == 3
    assert j["fired_count"] == 2
    assert len(j["results"]) == 3
    assert j["results"][0]["fired"] is True
    assert j["results"][1]["fired"] is False
    assert j["results"][2]["fired"] is True


def test_batch_simulation_empty_facts() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations/batch",
        json={
            "drl": "rule r when $t : T ( true ) then end",
            "facts": [],
        },
    )
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_batch_simulation_bad_drl() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/simulations/batch",
        json={
            "drl": "not valid drl {{",
            "facts": [{"t": {}}],
        },
    )
    assert r.status_code == 200
    assert r.json()["results"][0]["error"] is not None


# --- OPA/Rego export ---


def test_opa_export_basic() -> None:
    drl = 'rule "test-rule" when $f : Fact( $f.x > 10 ) then result.ok = true; end'
    rego = export_to_rego(drl)
    assert "package sparkrules.policy" in rego
    assert "test_rule = result" in rego
    assert "input.x > 10" in rego
    assert '"ok": true' in rego


def test_opa_export_custom_package() -> None:
    drl = "rule r when $f : Fact( true ) then result.v = 1; end"
    rego = export_to_rego(drl, package_name="myorg.rules")
    assert "package myorg.rules" in rego


def test_opa_export_reason_codes() -> None:
    drl = 'rule r reason_codes ["RC1", "RC2"] when $f : Fact( true ) then end'
    rego = export_to_rego(drl)
    assert "RC1" in rego
    assert "RC2" in rego


def test_opa_export_multiple_rules() -> None:
    drl = """
rule a when $f : Fact( $f.x > 1 ) then result.a = 1; end
rule b when $f : Fact( $f.y == "yes" ) then result.b = 2; end
"""
    rego = export_to_rego(drl)
    assert "# Rules: 2" in rego
    assert "a = result" in rego
    assert "b = result" in rego


def test_opa_expr_coverage() -> None:
    # Literal types
    assert _expr_to_rego(Literal("hello")) == '"hello"'
    assert _expr_to_rego(Literal(42)) == "42"
    assert _expr_to_rego(Literal(True)) == "true"
    assert _expr_to_rego(Literal(False)) == "false"
    assert _expr_to_rego(Literal(None)) == "null"

    # Not
    inner = Literal(True)
    assert "not" in _expr_to_rego(Not(inner))

    # InExpr with list
    in_expr = InExpr(Literal("a"), ListExpr((Literal("a"), Literal("b"))), negated=False)
    result = _expr_to_rego(in_expr)
    assert '"a"' in result

    # InExpr negated
    in_neg = InExpr(Literal("x"), ListExpr((Literal("y"),)), negated=True)
    assert "not" in _expr_to_rego(in_neg)

    # CallExpr
    call = CallExpr("myfunc", (Literal(1), Literal(2)))
    assert "myfunc(1, 2)" == _expr_to_rego(call)

    # ListExpr
    lst = ListExpr((Literal(1), Literal(2)))
    assert _expr_to_rego(lst) == "[1, 2]"


def test_opa_rule_no_actions() -> None:
    drl = "rule r when $f : Fact( true ) then end"
    ast = parse(drl)
    rego = _rule_to_rego(ast)
    assert '"fired": true' in rego


# --- Coverage for uncovered opa.py branches ---

from sparkrules.parser.ast import BinaryOp, BinaryOperator, Identifier


def test_opa_identifier_single_part() -> None:
    # Line 46: single-part identifier (no dots)
    assert _expr_to_rego(Identifier("x")) == "input.x"


def test_opa_identifier_dollar_prefix() -> None:
    assert _expr_to_rego(Identifier("$f")) == "input.f"


def test_opa_identifier_dotted() -> None:
    assert _expr_to_rego(Identifier("$f.amount")) == "input.amount"


def test_opa_binary_and() -> None:
    expr = BinaryOp(BinaryOperator.AND, Literal(True), Literal(False))
    result = _expr_to_rego(expr)
    assert "true" in result and "false" in result


def test_opa_binary_or() -> None:
    expr = BinaryOp(BinaryOperator.OR, Literal(True), Literal(False))
    result = _expr_to_rego(expr)
    assert "OR branch" in result


def test_opa_binary_contains() -> None:
    expr = BinaryOp(BinaryOperator.CONTAINS, Identifier("tags"), Literal("vip"))
    result = _expr_to_rego(expr)
    assert "[_]" in result


def test_opa_binary_matches() -> None:
    expr = BinaryOp(BinaryOperator.MATCHES, Identifier("name"), Literal("^J.*"))
    result = _expr_to_rego(expr)
    assert "regex.match" in result


def test_opa_in_expr_non_list_right() -> None:
    # InExpr where right side is not a ListExpr
    in_expr = InExpr(Literal("x"), Identifier("allowed"), negated=False)
    result = _expr_to_rego(in_expr)
    assert "input.allowed" in result

    in_neg = InExpr(Literal("x"), Identifier("blocked"), negated=True)
    result_neg = _expr_to_rego(in_neg)
    assert "not" in result_neg


def test_opa_unsupported_expr_type() -> None:
    # A type that _expr_to_rego doesn't handle
    class FakeExpr:
        pass

    result = _expr_to_rego(FakeExpr())  # type: ignore[arg-type]
    assert "unsupported" in result
